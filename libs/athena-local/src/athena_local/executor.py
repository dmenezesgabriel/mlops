"""Async query execution lifecycle (ADR-0009).

``QueryExecutor`` owns the QUEUED → RUNNING → terminal machine: ``start``
delegates the submit-time decisions (replay, reuse, statement mapping,
manifest capture, and the bounded submit + one-nextUri preflight that makes
bad SQL a 400 like real Athena's StartQueryExecution rejection) to
``submission.SubmissionPlanner``, then returns the execution immediately
(matching Athena and wrangler's poll loop); a background task drives the
Trino statement protocol until completion, and the terminal SUCCEEDED
transition fires only after the injected :class:`ResultArtifactWriter`
persisted the artifacts (ADR-0007, ADR-0009 #4). Trino-speak stops here and
in ``submission``: handlers depend on the executor, never on
``trino_client`` (architecture §8.5).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Protocol

from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
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
from athena_local.iceberg_probe import IcebergTableProbe
from athena_local.result_shapes import to_athena_result_shape
from athena_local.statement_classification import StatementClassification
from athena_local.submission import (
    TRINO_USER,
    ManifestSnapshotSource,
    StartRequest,
    StatementClient,
    SubmissionPlanner,
)
from athena_local.trino_client import (
    TrinoPage,
    TrinoQueryError,
    TrinoTransportError,
)

logger = logging.getLogger("athena_local")

DEFAULT_MAX_CONCURRENT_QUERIES = 4


class ResultArtifactWriter(Protocol):
    """Persists an execution's result artifacts before SUCCEEDED (ADR-0007).

    Implemented by ``artifacts.py`` for the wire byte format; the executor
    treats ``ArtifactWriteError`` as a failed execution so consumers never
    see SUCCEEDED without readable files (ADR-0009 #4).
    """

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None: ...


class ArtifactWriteError(Exception):
    """Result artifacts could not be persisted; the execution stays failed."""


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
        iceberg_probe: IcebergTableProbe | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._writer = writer
        self._semaphore = asyncio.Semaphore(max_concurrent_queries)
        self._snapshotter = snapshotter
        self._planner = SubmissionPlanner(
            store,
            client,
            snapshotter=snapshotter,
            iceberg_probe=iceberg_probe,
            trino_user=trino_user,
        )
        self._tasks: dict[str, asyncio.Task[None]] = {}
        # (workgroup, ClientRequestToken) → lock serializing the
        # resolve→create window of a token submit; the user count lets the
        # entries drop once the last user leaves, keeping the map bounded.
        self._token_submit_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._token_submit_users: dict[tuple[str, str], int] = {}
        # In-flight artifact writes by execution id, so cancel() can abort a
        # write parked at an await — otherwise a StopQueryExecution landing
        # inside writer.write leaves artifacts on a CANCELLED record.
        self._write_tasks: dict[str, asyncio.Task[None]] = {}

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

        The submit path lives in ``submission.SubmissionPlanner`` — replay of
        an idempotent token, a FAILED record for an unresolvable EXECUTE
        (real Athena fails those, it never 400s them), result reuse, the
        statement mapping, manifest capture and the bounded preflight. The
        classification is captured at submit time, matching how real Athena
        reports StatementType/SubstatementType even for failed executions.
        ``resolved_statement`` is the SQL actually submitted — a submitted
        ``EXECUTE`` names a stored statement, but Trino's protocol has no
        prepared-statement persistence, so the resolver's bound copy runs
        instead. Requires a running asyncio loop (FastAPI serves on one).
        """
        return await self._submit(
            StartRequest(
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
                resolution_failure_reason=resolution_failure_reason,
                result_reuse_configuration=result_reuse_configuration,
            )
        )

    async def _submit(self, request: StartRequest) -> QueryExecutionRecord:
        """The submit critical section, serialized per request token.

        Tokenless requests run unguarded; a ClientRequestToken submit holds
        the (workgroup, token) lock across resolve→create so a concurrent
        retry observes the original's record and replays it instead of
        double-submitting (service-2.json StartQueryExecution idempotency).
        """
        token = request.client_request_token
        if token is None:
            return await self._resolve_or_submit(request)
        async with self._token_submit_lock(request.workgroup, token):
            return await self._resolve_or_submit(request)

    @asynccontextmanager
    async def _token_submit_lock(
        self, workgroup: str, token: str
    ) -> AsyncIterator[None]:
        """Serialize same-token submits while their token is in flight.

        Two concurrent retries of one ClientRequestToken must not both pass
        the token lookup before either creates its record; the second waits
        here, then replays the first's record. Locks are refcounted so
        unique tokens never accumulate entries.
        """
        key = (workgroup, token)
        lock = self._token_submit_locks.setdefault(key, asyncio.Lock())
        self._token_submit_users[key] = (
            self._token_submit_users.get(key, 0) + 1
        )
        try:
            async with lock:
                yield
        finally:
            users = self._token_submit_users[key] - 1
            if users:
                self._token_submit_users[key] = users
            else:
                del self._token_submit_users[key]
                del self._token_submit_locks[key]

    async def _resolve_or_submit(
        self, request: StartRequest
    ) -> QueryExecutionRecord:
        record = self._planner.resolve_record(request)
        if record is not None:
            return record
        prepared = await self._planner.prepare(request)
        record = self._planner.create_record(request, prepared)
        if prepared.failure_reason is not None:
            record.transition_to(FAILED, prepared.failure_reason)
            return record
        assert (
            prepared.page is not None
        )  # page is forwarded exactly when no failure
        self._dispatch(record, prepared.page)
        return record

    def _dispatch(self, record: QueryExecutionRecord, page: TrinoPage) -> None:
        task = asyncio.create_task(self._execute(record, page))
        self._tasks[record.query_execution_id] = task
        task.add_done_callback(
            lambda done: self._reap_task(record.query_execution_id, done)
        )

    def _reap_task(self, execution_id: str, task: asyncio.Task[None]) -> None:
        """Drop the finished task and surface an unexpected death.

        Popping without retrieving left a crashed runner's exception
        unobserved until GC (the cancel-during-write window died silently
        this way); the log line is the failure's only surface — runners
        have no caller.
        """
        self._tasks.pop(execution_id, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "query execution %s runner failed",
                execution_id,
                exc_info=error,
            )

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
        # Abort a parked artifact write before the DELETE await can let it
        # finish — a CANCELLED record must not gain artifacts.
        in_flight_write = self._write_tasks.get(query_execution_id)
        if in_flight_write is not None:
            in_flight_write.cancel()
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
            if _cancelled(record):
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
        write = asyncio.create_task(self._writer.write(record, page))
        self._write_tasks[record.query_execution_id] = write
        try:
            await write
        except asyncio.CancelledError:
            if _cancelled(record):
                # cancel() aborted the parked write — no artifacts landed.
                return
            raise
        except ArtifactWriteError as error:
            if _cancelled(record):
                # The stop raced the write's failure; CANCELLED stands.
                return
            record.transition_to(
                FAILED, f"Result artifact write failed: {error}"
            )
            return
        finally:
            self._write_tasks.pop(record.query_execution_id, None)
        if _cancelled(record):
            # A writer without await points completes atomically — the
            # artifacts exist, but the record must not resurrect to
            # SUCCEEDED.
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


def _cancelled(record: QueryExecutionRecord) -> bool:
    # Read through a function boundary on purpose: pyright narrows state to
    # QUEUED above the transition_to/await chain, but StopQueryExecution can
    # race the runner and set CANCELLED while _poll_to_end was in flight.
    return record.state == CANCELLED
