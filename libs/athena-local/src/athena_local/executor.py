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
from dataclasses import dataclass, replace
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
from athena_local.output_targets import (
    ManifestTargetError,
    OutputSnapshot,
)
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import TrinoPage, TrinoTransportError

TRINO_CATALOG = "hive"
TRINO_USER = "athena-local"
DEFAULT_MAX_CONCURRENT_QUERIES = 4


class StatementClient(Protocol):
    """The Trino statement-protocol surface the executor drives.

    ``TrinoClient`` implements it structurally; tests inject scripted fakes
    for F.I.R.S.T. lifecycle tests (no docker). Parameter names mirror the
    concrete transports so pyright can type-check the composition root
    (``main.build_query_executor``, PC-6).
    """

    async def submit_statement(
        self, query: str, catalog: str, schema: str, user: str
    ) -> TrinoPage: ...

    async def fetch_next(self, next_uri: str) -> TrinoPage: ...

    async def cancel(self, next_uri: str) -> None: ...


class ResultArtifactWriter(Protocol):
    """Persists an execution's result artifacts before SUCCEEDED (ADR-0007).

    Implemented by ``artifacts.py`` for the wire byte format; the executor
    treats ``ArtifactWriteError`` as a failed execution so consumers never
    see SUCCEEDED without readable files (ADR-0009 #4).
    """

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None: ...


class ManifestSnapshotSource(Protocol):
    """Resolves and snapshots an INSERT/UNLOAD write target before submit.

    Implemented by ``output_targets.OutputSnapshotter`` (GlueProxy + S3Writer
    boundaries); the executor only records the outcome. Returns None for
    statements whose artifacts need no manifest enumeration — CTAS keeps its
    fresh external_location path.
    """

    async def capture(
        self,
        query: str,
        database: str | None,
        catalog: str | None,
        substatement_type: str | None,
    ) -> OutputSnapshot | None: ...


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
        snapshotter: ManifestSnapshotSource | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._writer = writer
        self._semaphore = asyncio.Semaphore(max_concurrent_queries)
        self._trino_user = trino_user
        self._snapshotter = snapshotter
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
        resolved_statement: str | None = None,
        resolution_failure_reason: str | None = None,
    ) -> QueryExecutionRecord:
        """Validate against Trino, create a QUEUED execution, dispatch it.

        A bounded preflight (submit + one nextUri fetch, ADR-0009 #2)
        mirrors real Athena: StartQueryExecution rejects syntactically
        invalid SQL with the exact 400 before any execution exists, yet still
        returns the execution ID without waiting for the query to run. The
        statement classification is captured at submit time, matching how
        real Athena reports StatementType/SubstatementType even for failed
        executions. ``resolved_statement`` is the SQL actually submitted — a
        submitted ``EXECUTE`` names a stored statement, but Trino's protocol
        has no prepared-statement persistence (QE-7), so the resolver's bound
        copy runs instead. A ``resolution_failure_reason`` (missing statement
        or parameter-count mismatch) skips manifest capture and preflight and
        starts the execution FAILED immediately: real Athena fails such
        EXECUTEs, it never 400s them. Requires a running asyncio loop
        (FastAPI serves on one).
        """
        if resolution_failure_reason is not None:
            record = self._create_record(
                query=query,
                workgroup=workgroup,
                database=database,
                catalog=catalog,
                result_configuration=result_configuration,
                execution_parameters=execution_parameters,
                statement_classification=statement_classification,
                resolved_statement=None,
            )
            record.transition_to(FAILED, resolution_failure_reason)
            return record
        submit_query = resolved_statement or query
        snapshot, capture_error = await self._capture_manifest(
            submit_query, database, catalog, statement_classification
        )
        verdict = await self._preflight(submit_query, database)
        record = self._create_record(
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            result_configuration=result_configuration,
            execution_parameters=execution_parameters,
            statement_classification=statement_classification,
            resolved_statement=resolved_statement,
            output_snapshot=snapshot,
            manifest_target_error=capture_error,
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

    def _create_record(
        self,
        *,
        query: str,
        workgroup: str,
        database: str | None,
        catalog: str | None,
        result_configuration: ResultConfiguration | None,
        execution_parameters: list[str] | None,
        statement_classification: StatementClassification | None,
        resolved_statement: str | None,
        output_snapshot: OutputSnapshot | None = None,
        manifest_target_error: str | None = None,
    ) -> QueryExecutionRecord:
        """Create the execution record with the four submit-time wire fields."""
        return self._store.create(
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
            output_snapshot=output_snapshot,
            manifest_target_error=manifest_target_error,
            resolved_statement=resolved_statement,
        )

    async def _capture_manifest(
        self,
        query: str,
        database: str | None,
        catalog: str | None,
        classification: StatementClassification | None,
    ) -> tuple[OutputSnapshot | None, str | None]:
        """Snapshot INSERT/UNLOAD write targets before the statement is submitted.

        Trino starts writing as soon as the statement is submitted, so the
        before-list must land here, ahead of ``_preflight``; listing at
        completion would count this query's own files as pre-existing.
        An unresolvable target leaves a reason for the artifact writer
        instead of failing submit, so Trino's own analysis error surfaces
        first when the target truly does not exist.
        """
        substatement_type = (
            classification.substatement_type
            if classification is not None
            else None
        )
        if substatement_type not in {"INSERT", "UNLOAD"}:
            return None, None
        if self._snapshotter is None:
            return (
                None,
                f"no manifest snapshotter configured for {substatement_type} "
                "statements",
            )
        try:
            snapshot = await self._snapshotter.capture(
                query, database, catalog, substatement_type
            )
        except ManifestTargetError as error:
            return None, str(error)
        return snapshot, None

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
                fetched = await self._client.fetch_next(page.next_uri)
            except TrinoTransportError as error:
                return PreflightVerdict(
                    page=None, failure_reason=f"Trino unreachable: {error}"
                )
            # Rows can arrive as early as the POST response itself; keep them
            # by folding them into the page forwarded to the poll task.
            page = replace(fetched, data=[*page.data, *fetched.data])
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
        # Trino streams rows across intermediate statement pages and the final
        # FINISHED document carries none (measured against the running
        # coordinator), so accumulate every page's rows and return them on the
        # final page for ``_complete`` to cache (statement protocol).
        accumulated_rows = [row for row in first_page.data]
        page = first_page
        while True:
            next_uri = page.next_uri
            if next_uri is None:
                return replace(page, data=accumulated_rows)
            if record.state == CANCELLED:
                return replace(page, data=accumulated_rows)
            try:
                page = await self._client.fetch_next(next_uri)
            except TrinoTransportError as error:
                if record.state != CANCELLED:
                    record.transition_to(FAILED, f"Trino unreachable: {error}")
                return None
            accumulated_rows.extend(page.data)
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
