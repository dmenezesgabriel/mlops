"""Async query execution lifecycle (ADR-0009).

``QueryExecutor`` owns the QUEUED → RUNNING → terminal machine: ``start``
validates the statement against Trino (a bounded submit + one nextUri fetch,
mirroring how real Athena rejects bad syntax at StartQueryExecution, QE-5),
then returns the execution immediately (matching Athena and wrangler's poll
loop); a background task drives the Trino statement protocol until
completion, and the terminal SUCCEEDED transition fires only after the
injected :class:`ResultArtifactWriter` persisted the artifacts (ADR-0007,
ADR-0009 #4). Trino-speak stops here: handlers depend on the executor, never
on ``trino_client`` (architecture §8.5).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from athena_local.common_schemas import ResultConfiguration
from athena_local.error_mapping import (
    is_syntax_error,
    syntax_error_invalid_request,
)
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    TERMINAL_STATES,
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import TrinoPage, TrinoTransportError

TRINO_CATALOG = "hive"
TRINO_USER = "athena-local"
DEFAULT_MAX_CONCURRENT_QUERIES = 4


class StatementClient(Protocol):
    """The Trino statement-protocol surface the executor drives.

    ``TrinoClient`` implements it structurally; tests inject scripted fakes
    for F.I.R.S.T. lifecycle tests (no docker). Params are underscore-scoped
    because the interface documents the wire contract, not the parameter
    vocabulary of the concrete transport.
    """

    async def submit_statement(
        self, _query: str, _catalog: str, _schema: str, _user: str
    ) -> TrinoPage: ...

    async def fetch_next(self, _next_uri: str) -> TrinoPage: ...

    async def cancel(self, _next_uri: str) -> None: ...


class ResultArtifactWriter(Protocol):
    """Persists an execution's result artifacts before SUCCEEDED (ADR-0007).

    Implemented by ``artifacts.py`` for the wire byte format; the executor
    treats ``ArtifactWriteError`` as a failed execution so consumers never
    see SUCCEEDED without readable files (ADR-0009 #4).
    """

    async def write(
        self, _execution: QueryExecutionRecord, _final_page: TrinoPage
    ) -> None: ...


class ArtifactWriteError(Exception):
    """Result artifacts could not be persisted; the execution stays failed."""


@dataclass(frozen=True)
class PreflightVerdict:
    """Outcome of the start-time Trino check (ADR-0009 #2, QE-5).

    ``page`` is the QueryResults document the poll task resumes from — the
    statement is never re-submitted — or None when ``failure_reason`` is set
    and the execution must start FAILED because Trino was unreachable.
    """

    page: TrinoPage | None
    failure_reason: str | None


class QueryExecutor:
    """Bounded async runner for Athena query executions (ADR-0009)."""

    def __init__(
        self,
        store: ExecutionStore,
        client: StatementClient,
        writer: ResultArtifactWriter,
        max_concurrent_queries: int = DEFAULT_MAX_CONCURRENT_QUERIES,
        trino_user: str = TRINO_USER,
    ) -> None:
        self._store = store
        self._client = client
        self._writer = writer
        self._semaphore = asyncio.Semaphore(max_concurrent_queries)
        self._trino_user = trino_user
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(
        self,
        query: str,
        workgroup: str,
        database: str | None = None,
        catalog: str | None = None,
        result_configuration: ResultConfiguration | None = None,
        execution_parameters: list[str] | None = None,
        statement_classification: StatementClassification | None = None,
    ) -> QueryExecutionRecord:
        """Validate against Trino, create a QUEUED execution, dispatch it.

        A bounded preflight (submit + one nextUri fetch, ADR-0009 #2)
        mirrors real Athena: StartQueryExecution rejects syntactically
        invalid SQL with the exact 400 before any execution exists, yet still
        returns the execution ID without waiting for the query to run. The
        statement classification is captured at submit time, matching how
        real Athena reports StatementType/SubstatementType even for failed
        executions. Requires a running asyncio loop (FastAPI serves on one).
        """
        verdict = await self._preflight(query, database)
        record = self._store.create(
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            result_configuration=result_configuration,
            execution_parameters=execution_parameters,
            statement_type=(
                statement_classification.statement_type
                if statement_classification is not None
                else None
            ),
            substatement_type=(
                statement_classification.substatement_type
                if statement_classification is not None
                else None
            ),
        )
        if verdict.failure_reason is not None:
            record.transition_to(FAILED, verdict.failure_reason)
            return record
        assert (
            verdict.page is not None
        )  # page is forwarded exactly when no failure
        task = asyncio.create_task(self._execute(record, verdict.page))
        self._tasks[record.query_execution_id] = task
        task.add_done_callback(
            lambda _: self._tasks.pop(record.query_execution_id, None)
        )
        return record

    async def _preflight(
        self, query: str, database: str | None
    ) -> PreflightVerdict:
        """POST the statement and follow one nextUri (ADR-0009 #2, QE-5).

        Trino's first page is always clean; syntax failures surface on the
        first following page (measured), which bounds syntax detection to a
        single fetch. A SYNTAX_ERROR page becomes the submit-time 400
        (error_mapping); any other page is forwarded for the poll task to
        continue from, and a transport failure becomes an immediate FAILED
        reason so a dead coordinator degrades gracefully (DP-5).
        """
        try:
            first_page = await self._client.submit_statement(
                query, TRINO_CATALOG, database or "", self._trino_user
            )
        except TrinoTransportError as error:
            return PreflightVerdict(
                page=None, failure_reason=f"Trino unreachable: {error}"
            )
        page = first_page
        if page.next_uri is not None:
            try:
                page = await self._client.fetch_next(page.next_uri)
            except TrinoTransportError as error:
                return PreflightVerdict(
                    page=None, failure_reason=f"Trino unreachable: {error}"
                )
        if is_syntax_error(page.error):
            raise syntax_error_invalid_request(page.error)
        return PreflightVerdict(page=page, failure_reason=None)

    async def cancel(self, query_execution_id: str) -> QueryExecutionRecord:
        """Stop a QUEUED or RUNNING execution and mark it CANCELLED."""
        record = self._store.get(query_execution_id)
        record.transition_to(CANCELLED)
        await self._stop_statement(record)
        return record

    def ensure_query_finished(
        self, query_execution_id: str
    ) -> QueryExecutionRecord:
        """Return the record, or raise Athena's exact pre-finish 400.

        Inline result reads asked before completion must fail the same way
        real Athena does — ``InvalidRequestException`` 400 with the current
        state named (ADR-0008): wrangler's 1 s poll never trips it, but a
        genuinely premature ``GetQueryResults`` must.
        """
        record = self._store.get(query_execution_id)
        if record.state not in TERMINAL_STATES:
            raise InvalidRequestException(
                f"Query has not yet finished. Current state: {record.state}"
            )
        return record

    async def _execute(
        self, record: QueryExecutionRecord, first_page: TrinoPage
    ) -> None:
        async with self._semaphore:
            if record.state != QUEUED:
                # A cancel that beat the task, or a preflight failure the
                # caller already made terminal, disarms the runner (ADR-0009).
                return
            record.transition_to(RUNNING)
            record.active_next_uri = first_page.next_uri
            page = await self._poll_to_end(record, first_page)
            if page is None:
                return
            if record.state == CANCELLED:
                return
            if page.error is not None:
                record.transition_to(FAILED, page.error.message)
                return
            await self._complete(record, page)

    async def _poll_to_end(
        self, record: QueryExecutionRecord, first_page: TrinoPage
    ) -> TrinoPage | None:
        page = first_page
        while True:
            next_uri = page.next_uri
            if next_uri is None:
                return page
            if record.state == CANCELLED:
                return page
            try:
                page = await self._client.fetch_next(next_uri)
            except TrinoTransportError as error:
                if record.state != CANCELLED:
                    record.transition_to(FAILED, f"Trino unreachable: {error}")
                return None
            record.active_next_uri = page.next_uri

    async def _complete(
        self, record: QueryExecutionRecord, page: TrinoPage
    ) -> None:
        record.apply_engine_statistics(page.stats)
        record.cache_result_page(
            [(column.name, column.column_type) for column in page.columns],
            page.data,
        )
        try:
            await self._writer.write(record, page)
        except ArtifactWriteError as error:
            record.transition_to(
                FAILED, f"Result artifact write failed: {error}"
            )
            return
        record.transition_to(SUCCEEDED)

    async def _stop_statement(self, record: QueryExecutionRecord) -> None:
        """DELETE the active Trino statement; best-effort (ADR-0009 #5)."""
        next_uri = record.active_next_uri
        if next_uri is None:
            return
        try:
            await self._client.cancel(next_uri)
        except TrinoTransportError:
            # The execution is already terminal CANCELLED; a dead coordinator
            # must not turn a user-requested stop into a failure.
            return
