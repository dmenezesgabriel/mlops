"""In-memory query execution registry (ADR-0003, ADR-0009).

Every started query is an execution record here, matching moto's
``executions`` map plus the wire transition contract Athena's
``QueryExecutionState`` enum declares (service-2.json): ``QUEUED → RUNNING →
SUCCEEDED | FAILED | CANCELLED``, terminal states immutable. SUCCEEDED may
only fire after the executor persisted the result artifacts (ADR-0007, ADR-0009
#4), so read consumers never race missing S3 objects. The runtime counters
Athena surfaces in ``GetQueryExecution`` Statistics are copied verbatim from
the Trino statement-protocol ``StatementStats`` JSON (``processedBytes`` →
``DataScannedInBytes``, ``wallTimeMillis`` → ``EngineExecutionTimeInMillis``;
field names from the trino ``client/trino-client/.../StatementStats.java``
class).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from time import time

from athena_local.common_schemas import (
    ResultConfiguration,
    result_configuration_payload,
)
from athena_local.errors import InvalidRequestException

QUEUED = "QUEUED"
RUNNING = "RUNNING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

TERMINAL_STATES = frozenset({SUCCEEDED, FAILED, CANCELLED})

VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({RUNNING, CANCELLED}),
    RUNNING: frozenset({SUCCEEDED, FAILED, CANCELLED}),
    SUCCEEDED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}


@dataclass
class QueryExecutionRecord:
    """A stored query execution; the wire shape is built by ``to_payload``."""

    query_execution_id: str
    query: str
    workgroup: str
    database: str | None = None
    catalog: str | None = None
    result_configuration: ResultConfiguration | None = None
    execution_parameters: list[str] | None = None
    state: str = QUEUED
    state_change_reason: str | None = None
    submission_time: float = field(default_factory=time)
    completion_time: float | None = None
    engine_execution_time_ms: int | None = None
    data_scanned_bytes: int | None = None
    data_manifest_location: str | None = None
    statement_type: str | None = None
    # The final Trino page the executor stashed before the terminal transition
    # (ADR-0009 #4): GetQueryResults serves rows from here without re-reading
    # S3, matching Athena's inline results endpoint (ADR-0007).
    result_columns: list[tuple[str, str]] = field(default_factory=list)
    result_rows: list[list[object]] = field(default_factory=list)
    # The in-flight nextUri cursor the executor cancels against (ADR-0009);
    # never serialized to the wire.
    active_next_uri: str | None = None

    def transition_to(self, new_state: str, reason: str | None = None) -> None:
        """Move to ``new_state``; terminal states are immutable (ADR-0009)."""
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(
                f"Cannot transition query execution {self.query_execution_id} "
                f"from {self.state} to {new_state}"
            )
        self.state = new_state
        self.state_change_reason = reason
        if new_state in TERMINAL_STATES:
            self.completion_time = time()

    def apply_engine_statistics(self, stats: dict[str, object]) -> None:
        """Copy the Trino StatementStats counters Athena reports back."""
        processed_bytes = stats.get("processedBytes")
        if isinstance(processed_bytes, int):
            self.data_scanned_bytes = processed_bytes
        wall_time_ms = stats.get("wallTimeMillis")
        if isinstance(wall_time_ms, int):
            self.engine_execution_time_ms = wall_time_ms

    def cache_result_page(
        self,
        columns: list[tuple[str, str]],
        rows: list[list[object]],
    ) -> None:
        """Stash the final statement page as plain (name, type) + row lists.

        Cached in place of the TrinoPage itself so this module never sees
        trino_client types (architecture §8.5: only the executor speaks Trino).
        """
        self.result_columns = list(columns)
        self.result_rows = [list(row) for row in rows]

    def to_payload(self) -> dict[str, object]:
        """Serialize to the GetQueryExecution ``QueryExecution`` wire shape."""
        payload: dict[str, object] = {
            "QueryExecutionId": self.query_execution_id,
            "Query": self.query,
            "Status": self._status_payload(),
            "Statistics": self._statistics_payload(),
            "WorkGroup": self.workgroup,
        }
        if self.result_configuration is not None:
            payload["ResultConfiguration"] = result_configuration_payload(
                self.result_configuration
            )
        if self.database is not None or self.catalog is not None:
            payload["QueryExecutionContext"] = self._context_payload()
        if self.statement_type is not None:
            payload["StatementType"] = self.statement_type
        if self.execution_parameters is not None:
            payload["ExecutionParameters"] = self.execution_parameters
        return payload

    def _status_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "State": self.state,
            "SubmissionDateTime": self.submission_time,
        }
        if self.state_change_reason is not None:
            payload["StateChangeReason"] = self.state_change_reason
        if self.completion_time is not None:
            payload["CompletionDateTime"] = self.completion_time
        return payload

    def _context_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {}
        if self.database is not None:
            payload["Database"] = self.database
        if self.catalog is not None:
            payload["Catalog"] = self.catalog
        return payload

    def _statistics_payload(self) -> dict[str, object]:
        # Real Athena always reports these counters; wrangler's cache flow
        # reads DataScannedInBytes without an existence check
        # (research_repos/aws-sdk-pandas/awswrangler/athena/_cache.py), so 0
        # must be present rather than the member being absent (ADR-0007).
        payload: dict[str, object] = {
            "DataScannedInBytes": self.data_scanned_bytes or 0,
            "EngineExecutionTimeInMillis": self.engine_execution_time_ms or 0,
        }
        if self.data_manifest_location is not None:
            payload["DataManifestLocation"] = self.data_manifest_location
        return payload


@dataclass
class ExecutionStore:
    """In-memory query execution registry; single-process, race-free (ADR-0003)."""

    by_id: dict[str, QueryExecutionRecord] = field(
        default_factory=dict, init=False
    )

    def create(
        self,
        query: str,
        workgroup: str,
        database: str | None = None,
        catalog: str | None = None,
        result_configuration: ResultConfiguration | None = None,
        execution_parameters: list[str] | None = None,
    ) -> QueryExecutionRecord:
        execution_id = str(uuid.uuid4())
        record = QueryExecutionRecord(
            query_execution_id=execution_id,
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            result_configuration=result_configuration,
            execution_parameters=execution_parameters,
        )
        self.by_id[execution_id] = record
        return record

    def get(self, query_execution_id: str) -> QueryExecutionRecord:
        if query_execution_id not in self.by_id:
            raise InvalidRequestException(
                f"QueryExecution {query_execution_id} does not exist"
            )
        return self.by_id[query_execution_id]

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
            if query_execution_id in self.by_id:
                found.append(self.by_id[query_execution_id])
            else:
                unprocessed.append(query_execution_id)
        return found, unprocessed
