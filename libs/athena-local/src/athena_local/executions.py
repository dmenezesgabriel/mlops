"""In-memory query execution registry (ADR-0003, ADR-0009).

``ExecutionStore`` owns every started query's record — the record type,
state constants and transition matrix live in ``execution_record`` and are
re-exported here so the registry is the single import surface. Retention
mirrors the real service: terminal records leave query history after AWS's
documented 45-day window and read as absent from every lookup, and the
store bounds retained history by count so a long-lived process stays
memory-flat (ADR-0003's in-memory control plane makes the process's own
footprint the bound that matters).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from time import time

from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
)
from athena_local.errors import InvalidRequestException
from athena_local.execution_record import (
    CANCELLED,
    FAILED,
    QUERY_HISTORY_TTL_SECONDS,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    TERMINAL_STATES,
    QueryExecutionRecord,
)
from athena_local.output_targets import OutputSnapshot
from athena_local.pagination import offset_page
from athena_local.statement_classification import normalize_statement_text

__all__ = [
    "CANCELLED",
    "DEFAULT_MAX_RETAINED_EXECUTIONS",
    "FAILED",
    "QUERY_HISTORY_TTL_SECONDS",
    "QUEUED",
    "RUNNING",
    "SUCCEEDED",
    "TERMINAL_STATES",
    "ExecutionStore",
    "QueryExecutionRecord",
]

# AWS bounds history by time alone; the emulator additionally caps retained
# executions so process memory stays bounded at any submission volume. The
# divergence is observable only beyond the cap inside one history window.
DEFAULT_MAX_RETAINED_EXECUTIONS = 10_000


@dataclass
class ExecutionStore:
    """In-memory query execution registry; single-process, race-free (ADR-0003).

    Retention mirrors AWS's query-history bound: terminal records expire
    45 days after completion (``QUERY_HISTORY_TTL_SECONDS``) and read as
    absent from every lookup, while ``max_retained_executions`` evicts the
    oldest terminal records on ``create`` so memory stays bounded inside
    the window. In-flight records are never evicted — the executor still
    owns them — so the store may exceed the cap by the live count.
    """

    max_retained_executions: int = DEFAULT_MAX_RETAINED_EXECUTIONS
    by_id: dict[str, QueryExecutionRecord] = field(
        default_factory=dict, init=False
    )
    # (workgroup, ClientRequestToken) → execution id backing the model's
    # idempotent-submit contract (service-2.json StartQueryExecution): a
    # retried token replays the original response instead of re-executing.
    by_request_token: dict[tuple[str, str], str] = field(
        default_factory=dict, init=False
    )

    def __post_init__(self) -> None:
        if self.max_retained_executions < 1:
            raise ValueError(
                "max_retained_executions must be a positive integer, "
                f"got {self.max_retained_executions!r}"
            )

    def reset(self) -> None:
        """Drop every query execution (test reset point, ADR-0003)."""
        self.by_id.clear()
        self.by_request_token.clear()

    def create(
        self,
        query: str,
        workgroup: str,
        database: str | None = None,
        catalog: str | None = None,
        result_configuration: ResultConfiguration | None = None,
        managed_results: bool = False,
        execution_parameters: list[str] | None = None,
        client_request_token: str | None = None,
        statement_type: str | None = None,
        substatement_type: str | None = None,
        output_snapshot: OutputSnapshot | None = None,
        manifest_target_error: str | None = None,
        resolved_statement: str | None = None,
        result_reuse_configuration: ResultReuseByAgeConfiguration
        | None = None,
        unload_cleanup_table: tuple[str, str] | None = None,
        partition_noop_on_exists: bool = False,
    ) -> QueryExecutionRecord:
        execution_id = str(uuid.uuid4())
        record = QueryExecutionRecord(
            query_execution_id=execution_id,
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            result_configuration=result_configuration,
            managed_results=managed_results,
            execution_parameters=execution_parameters,
            statement_type=statement_type,
            substatement_type=substatement_type,
            output_snapshot=output_snapshot,
            manifest_target_error=manifest_target_error,
            resolved_statement=resolved_statement,
            result_reuse_configuration=result_reuse_configuration,
            unload_cleanup_table=unload_cleanup_table,
            partition_noop_on_exists=partition_noop_on_exists,
            request_token=client_request_token,
        )
        self.by_id[execution_id] = record
        if client_request_token is not None:
            # First-wins: the executor's dedup check normally prevents a
            # second create, but a raced duplicate still replays the
            # original id.
            self.by_request_token.setdefault(
                (workgroup, client_request_token), execution_id
            )
        self._evict_over_retention_cap()
        return record

    def _evict_over_retention_cap(self) -> None:
        """Evict oldest terminal executions until the store is within cap.

        Insertion order is submission order, so the front scan reaches
        finished records first in steady state (amortized ~1 per create);
        QUEUED/RUNNING records are in-flight work the executor still owns
        and are skipped, leaving the store past cap by the live count.
        """
        excess = len(self.by_id) - self.max_retained_executions
        if excess <= 0:
            return
        evicted_ids: list[str] = []
        for execution_id, record in self.by_id.items():
            if len(evicted_ids) >= excess:
                break
            if record.state in TERMINAL_STATES:
                evicted_ids.append(execution_id)
        for execution_id in evicted_ids:
            self._drop_execution(execution_id)

    def _drop_execution(self, execution_id: str) -> None:
        """Remove a record and its ClientRequestToken mapping, if it owns one.

        First-wins ``setdefault`` can leave a token pointing at a different
        record, so the entry is deleted only when it names the evicted id —
        and must be deleted then, or a dead id would wedge every later
        retry of the token into re-executing without re-registering.
        """
        record = self.by_id.pop(execution_id)
        if record.request_token is None:
            return
        key = (record.workgroup, record.request_token)
        if self.by_request_token.get(key) == execution_id:
            del self.by_request_token[key]

    def find_by_request_token(
        self, workgroup: str, client_request_token: str
    ) -> QueryExecutionRecord | None:
        """The execution a (workgroup, ClientRequestToken) retry replays.

        A token whose original execution evicted or expired out of history
        no longer replays: the stale entry is dropped so a retry runs fresh
        and re-registers, matching AWS's retention-bounded idempotency.
        """
        key = (workgroup, client_request_token)
        execution_id = self.by_request_token.get(key)
        if execution_id is None:
            return None
        record = self._retained_execution(execution_id)
        if record is None:
            del self.by_request_token[key]
            return None
        return record

    def _retained_execution(
        self, query_execution_id: str
    ) -> QueryExecutionRecord | None:
        """The record only while it is inside the 45-day history window."""
        record = self.by_id.get(query_execution_id)
        if record is None or record.is_retention_expired(time()):
            return None
        return record

    def get(self, query_execution_id: str) -> QueryExecutionRecord:
        record = self._retained_execution(query_execution_id)
        if record is None:
            raise InvalidRequestException(
                f"QueryExecution {query_execution_id} does not exist"
            )
        return record

    def find_reusable(
        self,
        *,
        workgroup: str,
        query: str,
        database: str | None,
        catalog: str | None,
        execution_parameters: list[str] | None,
        result_configuration: ResultConfiguration | None,
        max_age_minutes: int,
    ) -> QueryExecutionRecord | None:
        """Newest SUCCEEDED execution matching Athena's reuse conditions.

        Result reuse re-answers a query when a previous execution in the
        same workgroup ran a statement identical modulo comments and
        whitespace, in the same database/catalog, with the same execution
        parameters and the same result configuration, completed within the
        request's ``MaxAgeInMinutes`` (AWS UG "Reusing query results").
        """
        query_key = normalize_statement_text(query)
        now = time()
        oldest_allowed = now - max_age_minutes * 60
        for record in reversed(self.by_id.values()):
            if record.is_retention_expired(now):
                continue
            if record.state != SUCCEEDED:
                continue
            if (record.completion_time or 0) < oldest_allowed:
                continue
            if record.matches_reuse_identity(
                workgroup=workgroup,
                query_key=query_key,
                database=database,
                catalog=catalog,
                execution_parameters=execution_parameters,
                result_configuration=result_configuration,
            ):
                return record
        return None

    def batch_get(
        self, query_execution_ids: list[str]
    ) -> tuple[list[QueryExecutionRecord], list[str]]:
        """Split the requested IDs into found records and missing IDs.

        BatchGetQueryExecution answers per-item: found records are returned
        and missing ones surface as ``UnprocessedQueryExecutionIds`` instead
        of failing the whole call (model BatchGetQueryExecutionOutput).
        """
        found: list[QueryExecutionRecord] = []
        unprocessed: list[str] = []
        for query_execution_id in query_execution_ids:
            record = self._retained_execution(query_execution_id)
            if record is None:
                unprocessed.append(query_execution_id)
                continue
            found.append(record)
        return found, unprocessed

    def list_execution_ids(
        self,
        workgroup: str,
        max_results: int | None = None,
        next_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return execution IDs for a workgroup, most recent first.

        Mirrors the named-query store's offset pagination: ``next_token`` is
        the opaque zero-based start index and the returned token names the
        next start, so botocore's list_query_executions paginator (the path
        wrangler's Athena cache probe walks — awswrangler/athena/_cache.py
        :113-129) merges pages losslessly. AWS documents the newest first.
        """
        now = time()
        newest_first = [
            execution_id
            for execution_id, record in reversed(self.by_id.items())
            if record.workgroup == workgroup
            and not record.is_retention_expired(now)
        ]
        return offset_page(newest_first, max_results, next_token)
