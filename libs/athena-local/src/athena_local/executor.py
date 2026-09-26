"""Async query execution lifecycle (ADR-0009).

``QueryExecutor`` owns the QUEUED → RUNNING → terminal machine: ``start``
validates the statement against Trino (a bounded submit + one nextUri fetch,
mirroring how real Athena rejects bad syntax at StartQueryExecution),
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

from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
)
from athena_local.dialect import to_trino_dialect, unload_trino_submission
from athena_local.error_mapping import (
    is_syntax_error,
    syntax_error_invalid_request,
)
from athena_local.errors import (
    InternalServerException,
    InvalidRequestException,
)
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
from athena_local.partition_alter import add_partition_trino_call
from athena_local.result_shapes import to_athena_result_shape
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import (
    TrinoPage,
    TrinoQueryError,
    TrinoTransportError,
)

TRINO_CATALOG = "hive"
TRINO_USER = "athena-local"
DEFAULT_MAX_CONCURRENT_QUERIES = 4


class StatementClient(Protocol):
    """The Trino statement-protocol surface the executor drives.

    ``TrinoClient`` implements it structurally; tests inject scripted fakes
    for F.I.R.S.T. lifecycle tests (no docker). Parameter names mirror the
    concrete transports so pyright can type-check the composition root
    (``main.build_query_executor``).
    """

    async def submit_statement(
        self,
        query: str,
        catalog: str,
        schema: str,
        user: str,
        session_properties: dict[str, str] | None = None,
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

    def drop_table(self, database: str, table: str) -> None:
        """Remove a transient catalog entry (the UNLOAD temp table)."""
        ...


class ArtifactWriteError(Exception):
    """Result artifacts could not be persisted; the execution stays failed."""


@dataclass(frozen=True)
class PreflightVerdict:
    """Outcome of the start-time Trino check (ADR-0009 #2).

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
        managed_results: bool = False,
        execution_parameters: list[str] | None = None,
        client_request_token: str | None = None,
        statement_classification: StatementClassification | None = None,
        resolved_statement: str | None = None,
        resolution_failure_reason: str | None = None,
        result_reuse_configuration: ResultReuseByAgeConfiguration
        | None = None,
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
        has no prepared-statement persistence, so the resolver's bound
        copy runs instead. A ``resolution_failure_reason`` (missing statement
        or parameter-count mismatch) skips manifest capture and preflight and
        starts the execution FAILED immediately: real Athena fails such
        EXECUTEs, it never 400s them. A ``client_request_token`` replays an
        earlier identical submission under the model's idempotency contract
        instead of starting anything. Requires a running asyncio loop
        (FastAPI serves on one).
        """
        replayed = self._request_token_replay(
            client_request_token,
            workgroup,
            query=query,
            database=database,
            catalog=catalog,
            execution_parameters=execution_parameters,
            result_configuration=result_configuration,
            result_reuse_configuration=result_reuse_configuration,
        )
        if replayed is not None:
            return replayed
        if resolution_failure_reason is not None:
            record = self._create_record(
                query=query,
                workgroup=workgroup,
                database=database,
                catalog=catalog,
                result_configuration=result_configuration,
                managed_results=managed_results,
                execution_parameters=execution_parameters,
                client_request_token=client_request_token,
                statement_classification=statement_classification,
                resolved_statement=None,
                result_reuse_configuration=result_reuse_configuration,
            )
            record.transition_to(FAILED, resolution_failure_reason)
            return record
        reusable = self._reusable_source(
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            execution_parameters=execution_parameters,
            result_configuration=result_configuration,
            result_reuse_configuration=result_reuse_configuration,
            managed_results=managed_results,
            statement_classification=statement_classification,
        )
        if reusable is not None:
            record = self._create_record(
                query=query,
                workgroup=workgroup,
                database=database,
                catalog=catalog,
                result_configuration=result_configuration,
                managed_results=managed_results,
                execution_parameters=execution_parameters,
                client_request_token=client_request_token,
                statement_classification=statement_classification,
                resolved_statement=resolved_statement,
                result_reuse_configuration=result_reuse_configuration,
            )
            record.reuse_results_from(reusable)
            record.transition_to(RUNNING)
            record.transition_to(SUCCEEDED)
            return record
        submit_query = resolved_statement or query
        # UNLOAD has no Trino statement at all: the rewrite to a CTAS at the
        # TO path also names the temp table the completion path must drop
        # (dialect.py). Unsupported WITH properties reject here, mirroring
        # real Athena's submit-time validation.
        unload = unload_trino_submission(submit_query, database)
        # Athena's ``ALTER TABLE … ADD [IF NOT EXISTS] PARTITION`` has no
        # Trino grammar either — it maps to a ``register_partition`` CALL
        # whose ``IF NOT EXISTS`` flag rides the record (partition_alter.py).
        partition_call = add_partition_trino_call(submit_query, database)
        # Capture on the original statement text: the rewrite consumes the
        # very TO clause ``unload_location`` resolves for the manifest.
        snapshot, capture_error = await self._capture_manifest(
            submit_query, database, catalog, statement_classification
        )
        session_properties: dict[str, str] | None = None
        cleanup_table: tuple[str, str] | None = None
        partition_noop_on_exists = False
        if unload is not None:
            submit_query = unload.sql
            session_properties = unload.session_properties or None
            cleanup_table = unload.cleanup_table
        elif partition_call is not None:
            submit_query = partition_call.sql
            partition_noop_on_exists = partition_call.noop_if_exists
        else:
            # Athena accepts a few statements Trino's grammar rejects (e.g.
            # CREATE DATABASE, MSCK REPAIR TABLE); submit the dialect-mapped
            # form while the record keeps the query as written (dialect.py).
            # The database context feeds the rewrite's schema fallback.
            submit_query = to_trino_dialect(submit_query, database)
        verdict = await self._preflight(
            submit_query, database, session_properties
        )
        record = self._create_record(
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            result_configuration=result_configuration,
            managed_results=managed_results,
            execution_parameters=execution_parameters,
            client_request_token=client_request_token,
            statement_classification=statement_classification,
            resolved_statement=resolved_statement,
            output_snapshot=snapshot,
            manifest_target_error=capture_error,
            result_reuse_configuration=result_reuse_configuration,
            unload_cleanup_table=cleanup_table,
            partition_noop_on_exists=partition_noop_on_exists,
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

    def _request_token_replay(
        self,
        client_request_token: str | None,
        workgroup: str,
        *,
        query: str,
        database: str | None,
        catalog: str | None,
        execution_parameters: list[str] | None,
        result_configuration: ResultConfiguration | None,
        result_reuse_configuration: ResultReuseByAgeConfiguration | None,
    ) -> QueryExecutionRecord | None:
        """The earlier identical submission a ClientRequestToken replays.

        The canonical model marks StartQueryExecution idempotent
        (service-2.json): a retried token answers the original
        QueryExecutionId without re-executing, while the same token
        submitted with changed parameters errors instead.
        """
        if client_request_token is None:
            return None
        existing = self._store.find_by_request_token(
            workgroup, client_request_token
        )
        if existing is None:
            return None
        if not existing.same_request(
            query=query,
            database=database,
            catalog=catalog,
            execution_parameters=execution_parameters,
            result_configuration=result_configuration,
            result_reuse_configuration=result_reuse_configuration,
        ):
            raise InvalidRequestException(
                f"ClientRequestToken {client_request_token!r} was already "
                "used with different request parameters"
            )
        return existing

    def _reusable_source(
        self,
        *,
        query: str,
        workgroup: str,
        database: str | None,
        catalog: str | None,
        execution_parameters: list[str] | None,
        result_configuration: ResultConfiguration | None,
        result_reuse_configuration: ResultReuseByAgeConfiguration | None,
        managed_results: bool,
        statement_classification: StatementClassification | None,
    ) -> QueryExecutionRecord | None:
        """The previous execution Athena would re-answer for this request.

        Reuse applies only when the request enabled it, the statement
        produces a result set (SELECT, including a resolved
        EXECUTE-of-SELECT), and the workgroup doesn't own managed results;
        every other submission runs fresh (AWS UG "Reusing query results"
        considerations).
        """
        if (
            result_reuse_configuration is None
            or not result_reuse_configuration.enabled
        ):
            return None
        if managed_results:
            return None
        if (
            statement_classification is None
            or statement_classification.substatement_type != "SELECT"
        ):
            return None
        return self._store.find_reusable(
            workgroup=workgroup,
            query=query,
            database=database,
            catalog=catalog,
            execution_parameters=execution_parameters,
            result_configuration=result_configuration,
            max_age_minutes=result_reuse_configuration.max_age_in_minutes,
        )

    def _create_record(
        self,
        *,
        query: str,
        workgroup: str,
        database: str | None,
        catalog: str | None,
        result_configuration: ResultConfiguration | None,
        managed_results: bool,
        execution_parameters: list[str] | None,
        client_request_token: str | None,
        statement_classification: StatementClassification | None,
        resolved_statement: str | None,
        output_snapshot: OutputSnapshot | None = None,
        manifest_target_error: str | None = None,
        result_reuse_configuration: ResultReuseByAgeConfiguration
        | None = None,
        unload_cleanup_table: tuple[str, str] | None = None,
        partition_noop_on_exists: bool = False,
    ) -> QueryExecutionRecord:
        """Create the execution record with the four submit-time wire fields."""
        return self._store.create(
            query=query,
            workgroup=workgroup,
            database=database,
            catalog=catalog,
            result_configuration=result_configuration,
            managed_results=managed_results,
            execution_parameters=execution_parameters,
            client_request_token=client_request_token,
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
            result_reuse_configuration=result_reuse_configuration,
            unload_cleanup_table=unload_cleanup_table,
            partition_noop_on_exists=partition_noop_on_exists,
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
        self,
        query: str,
        database: str | None,
        session_properties: dict[str, str] | None = None,
    ) -> PreflightVerdict:
        """POST the statement and follow one nextUri (ADR-0009 #2).

        Trino's first page is always clean; syntax failures surface on the
        first following page (measured), which bounds syntax detection to a
        single fetch. A SYNTAX_ERROR page becomes the submit-time 400
        (error_mapping); any other page is forwarded for the poll task to
        continue from, and a transport failure becomes an immediate FAILED
        reason so a dead coordinator degrades gracefully.
        """
        try:
            first_page = await self._client.submit_statement(
                query,
                TRINO_CATALOG,
                database or "",
                self._trino_user,
                session_properties=session_properties,
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
        """Stop a QUEUED or RUNNING execution and mark it CANCELLED.

        The canonical model marks StopQueryExecution idempotent
        (service-2.json): a terminal execution is a 200 no-op — no state
        change, and no Trino DELETE for a statement that already finished.
        """
        record = self._store.get(query_execution_id)
        if record.state in TERMINAL_STATES:
            return record
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
                # An UNLOAD's parked CTAS may still have registered the
                # temp table server-side — best-effort drop, like the other
                # non-success exits below.
                self._drop_unload_table(record)
                return
            record.transition_to(RUNNING)
            record.active_next_uri = first_page.next_uri
            page = await self._poll_to_end(record, first_page)
            if page is None:
                self._drop_unload_table(record)
                return
            if record.state == CANCELLED:
                self._drop_unload_table(record)
                return
            if page.error is not None:
                self._drop_unload_table(record)
                if self._partition_exists_noop(record, page.error):
                    await self._complete(record, page)
                    return
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
        columns, rows = to_athena_result_shape(
            record.substatement_type,
            [(column.name, column.column_type) for column in page.columns],
            page.data,
        )
        record.cache_result_page(columns, rows)
        cleanup_error = self._unload_cleanup_error(record)
        if cleanup_error is not None:
            record.transition_to(FAILED, cleanup_error)
            return
        if record.managed_results:
            # Managed-results executions (ADR-0011) never expose S3 artifacts:
            # the workgroup's Athena-owned storage is invisible to consumers,
            # who read the rows inline via GetQueryResults. Succeeding still
            # requires the cached page above to be present.
            record.transition_to(SUCCEEDED)
            return
        try:
            await self._writer.write(record, page)
        except ArtifactWriteError as error:
            record.transition_to(
                FAILED, f"Result artifact write failed: {error}"
            )
            return
        record.transition_to(SUCCEEDED)

    def _partition_exists_noop(
        self, record: QueryExecutionRecord, error: TrinoQueryError
    ) -> bool:
        """Whether an ``IF NOT EXISTS`` partition add is AWS's no-op.

        The statement rewrote to ``system.register_partition``, whose
        ``ALREADY_EXISTS`` fires only when the partition is registered —
        before any mutation (procedure source) — which is exactly the
        guard's semantics on real Athena: keep the old registration,
        report success.
        """
        return (
            record.partition_noop_on_exists
            and error.error_name == "ALREADY_EXISTS"
        )

    def _unload_cleanup_error(
        self, record: QueryExecutionRecord
    ) -> str | None:
        """Drop the UNLOAD temp table before success; failure names a reason.

        The emitted CTAS registers a Glue entry real UNLOAD never has, so
        the drop is part of the statement's success semantics: consumers
        must not see SUCCEEDED over a catalog showing emulator litter (the
        same discipline as the artifact writer, ADR-0009 #4).
        """
        cleanup = record.unload_cleanup_table
        if cleanup is None:
            return None
        if self._snapshotter is None:
            return (
                "UNLOAD temp catalog table could not be dropped: "
                "no manifest snapshotter configured"
            )
        try:
            self._snapshotter.drop_table(*cleanup)
        except InternalServerException as error:
            return f"UNLOAD temp catalog table could not be dropped: {error}"
        return None

    def _drop_unload_table(self, record: QueryExecutionRecord) -> None:
        """Best-effort UNLOAD temp-table cleanup on a non-success exit.

        A cancelled or engine-failed CTAS may still have registered the
        table; the drop keeps the catalog clean, while its own failure is
        swallowed — the record is already terminal with the truer reason.
        """
        cleanup = record.unload_cleanup_table
        if cleanup is None or self._snapshotter is None:
            return
        try:
            self._snapshotter.drop_table(*cleanup)
        except InternalServerException:
            return

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
