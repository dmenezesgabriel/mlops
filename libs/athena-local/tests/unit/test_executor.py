"""Query execution lifecycle (executor.py) per ADR-0009.

The executor drives a ``QueryExecutionRecord`` QUEUED → RUNNING → terminal with
a real ``TrinoClient``-shaped dependency injected as a named fake (F.I.R.S.T.,
no docker): scripted pages for the happy/error paths, a gated fake for the
semaphore/cancellation windows. The terminal transition must only fire after
the artifact writer persisted the results (ADR-0009 #4), and inline reads on a
non-terminal execution raise Athena's exact 400 (ADR-0008 #3).
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.executor import (
    TRINO_CATALOG,
    TRINO_USER,
    ArtifactWriteError,
    QueryExecutor,
)
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import (
    TrinoColumn,
    TrinoPage,
    TrinoQueryError,
    TrinoTransportError,
)

QUERY_ID = "20260920_000000_00000_exec001"
URI_1 = f"http://trino:8080/v1/statement/{QUERY_ID}/1"
URI_2 = f"http://trino:8080/v1/statement/{QUERY_ID}/2"


def result_page(
    next_uri: str | None,
    data: list[list[object]] | None = None,
    columns: list[TrinoColumn] | None = None,
    error: TrinoQueryError | None = None,
    stats: dict[str, object] | None = None,
    update_type: str | None = None,
) -> TrinoPage:
    return TrinoPage(
        query_id=QUERY_ID,
        next_uri=next_uri,
        update_type=update_type,
        columns=columns if columns is not None else [],
        data=data if data is not None else [],
        stats=stats if stats is not None else {},
        error=error,
    )


class ScriptedStatementClient:
    """StatementClient fake serving scripted pages and recording every call."""

    def __init__(
        self,
        pages: list[TrinoPage],
        *,
        submit_delay_seconds: float = 0.0,
        fetch_delay_seconds: float = 0.0,
        submit_error: TrinoTransportError | None = None,
        fetch_error: TrinoTransportError | None = None,
        cancel_error: TrinoTransportError | None = None,
    ) -> None:
        self._pages = list(pages)
        self._submit_delay = submit_delay_seconds
        self._fetch_delay = fetch_delay_seconds
        self._submit_error = submit_error
        self._fetch_error = fetch_error
        self._cancel_error = cancel_error
        self.submissions: list[tuple[str, str, str, str]] = []
        self.fetches: list[str] = []
        self.cancellations: list[str] = []

    async def submit_statement(
        self, query: str, catalog: str, schema: str, user: str
    ) -> TrinoPage:
        self.submissions.append((query, catalog, schema, user))
        await self._pause(self._submit_delay)
        if self._submit_error is not None:
            raise self._submit_error
        return self._pages.pop(0)

    async def fetch_next(self, next_uri: str) -> TrinoPage:
        self.fetches.append(next_uri)
        await self._pause(self._fetch_delay)
        if self._fetch_error is not None:
            raise self._fetch_error
        return self._pages.pop(0)

    async def cancel(self, next_uri: str) -> None:
        self.cancellations.append(next_uri)
        if self._cancel_error is not None:
            raise self._cancel_error

    @staticmethod
    async def _pause(delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)


class GatedStatementClient:
    """StatementClient fake whose submission blocks on a shared event.

    Opens deterministic windows for semaphore-bound and cancellation tests: a
    task holding a semaphore slot parks inside ``submit_statement`` until the
    gate is released, so sibling tasks stay QUEUED at the semaphore.
    """

    def __init__(self, gate: asyncio.Event, query_id: str = QUERY_ID) -> None:
        self._gate = gate
        self._query_id = query_id
        self._active = 0
        self.peak_active = 0
        self.submission_count = 0

    async def submit_statement(
        self, query: str, catalog: str, schema: str, user: str
    ) -> TrinoPage:
        await self._gate.wait()
        self.submission_count += 1
        self._active += 1
        self.peak_active = max(self.peak_active, self._active)
        try:
            await asyncio.sleep(0.05)
            return result_page(next_uri=None, stats={"state": "FINISHED"})
        finally:
            self._active -= 1

    async def fetch_next(self, next_uri: str) -> TrinoPage:
        raise AssertionError("gated client never pages")

    async def cancel(self, next_uri: str) -> None:
        raise AssertionError("gated client is never cancelled")


class RecordingWriter:
    """ResultArtifactWriter fake that records the execution state it saw."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        self.calls.append(f"write:{execution.state}")


class FailingWriter:
    """ResultArtifactWriter fake that never manages to persist results."""

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        raise ArtifactWriteError("moto S3 refused put_object")


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_happy_path_polls_and_succeeds(store: ExecutionStore) -> None:
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "RUNNING"}),
                result_page(next_uri=URI_2, stats={"state": "RUNNING"}),
                result_page(
                    next_uri=None,
                    columns=[TrinoColumn(name="_col0", column_type="integer")],
                    data=[[1]],
                    stats={
                        "state": "FINISHED",
                        "processedBytes": 512,
                        "wallTimeMillis": 4,
                    },
                ),
            ]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            ("SELECT 1", TRINO_CATALOG, "", TRINO_USER)
        ]
        assert client.fetches == [URI_1, URI_2]
        assert record.state == SUCCEEDED
        assert record.data_scanned_bytes == 512
        assert record.engine_execution_time_ms == 4

    asyncio.run(scenario())
    assert writer.calls == [
        "write:RUNNING"
    ]  # writer saw RUNNING, before SUCCEEDED


def test_start_records_statement_classification(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        classification = StatementClassification(
            statement_type="DDL", substatement_type="CREATE_TABLE_AS_SELECT"
        )

        record = executor.start(
            query="CREATE TABLE db.t WITH (format='PARQUET') AS SELECT 1",
            workgroup="primary",
            statement_classification=classification,
        )
        await executor._tasks[record.query_execution_id]

        assert record.statement_type == "DDL"
        assert record.substatement_type == "CREATE_TABLE_AS_SELECT"

    asyncio.run(scenario())


def test_happy_path_submits_with_database_schema(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(
            query="SELECT 1", workgroup="primary", database="analytics"
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            ("SELECT 1", TRINO_CATALOG, "analytics", TRINO_USER)
        ]

    asyncio.run(scenario())


def test_submit_transport_error_marks_failed(store: ExecutionStore) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [],
            submit_error=TrinoTransportError("connection refused"),
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert "connection refused" in record.state_change_reason or ""

    asyncio.run(scenario())


def test_fetch_transport_error_marks_failed(store: ExecutionStore) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1)],
            fetch_delay_seconds=0.05,
            fetch_error=TrinoTransportError("read timeout"),
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert "read timeout" in record.state_change_reason or ""

    asyncio.run(scenario())


def test_failed_query_page_marks_failed(store: ExecutionStore) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=None,
                    error=TrinoQueryError(
                        message="line 1:1: mismatched input 'SELEC'",
                        error_type="USER_ERROR",
                        error_name="SYNTAX_ERROR",
                    ),
                )
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELEC", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert (
            record.state_change_reason == "line 1:1: mismatched input 'SELEC'"
        )

    asyncio.run(scenario())


def test_writer_failure_marks_failed_not_succeeded(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=FailingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert "moto S3 refused put_object" in (
            record.state_change_reason or ""
        )

    asyncio.run(scenario())


def test_cancel_queued_execution_never_touches_trino(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        client = GatedStatementClient(gate)
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            max_concurrent_queries=1,
        )
        first = executor.start(query="SELECT biggest", workgroup="primary")
        await asyncio.sleep(
            0.02
        )  # first now parks inside submit holding the slot
        queued = executor.start(query="SELECT cancelled", workgroup="primary")
        assert queued.state == QUEUED

        cancelled = await executor.cancel(queued.query_execution_id)

        assert cancelled.state == CANCELLED
        gate.set()
        await asyncio.gather(
            executor._tasks[first.query_execution_id],
            executor._tasks[queued.query_execution_id],
        )
        assert (
            client.submission_count == 1
        )  # queued execution was never dispatched
        assert first.state == SUCCEEDED
        assert queued.state == CANCELLED

    asyncio.run(scenario())


def test_cancel_running_execution_deletes_statement(
    store: ExecutionStore,
) -> None:
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "RUNNING"}),
                result_page(next_uri=URI_2, stats={"state": "RUNNING"}),
                result_page(next_uri=None, data=[[1]]),
            ],
            fetch_delay_seconds=0.05,
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # first page fetched, now polling URI_1

        cancelled = await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert cancelled.state == CANCELLED
        assert client.cancellations == [URI_1]
        assert writer.calls == []

    asyncio.run(scenario())


def test_canceled_then_fetch_error_stays_cancelled(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1)],
            fetch_delay_seconds=0.05,
            fetch_error=TrinoTransportError("coordinator gone"),
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # actively waiting on fetch_next(URI_1)

        await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert record.state == CANCELLED  # transport error must not win

    asyncio.run(scenario())


def test_cancel_while_submit_pending_still_deletes(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1)],
            submit_delay_seconds=0.05,
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # still inside submit_statement

        await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert record.state == CANCELLED
        assert client.cancellations == [URI_1]

    asyncio.run(scenario())


def test_cancel_survives_trino_down_on_delete(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(next_uri=URI_2),
                result_page(next_uri=None),
            ],
            fetch_delay_seconds=0.05,
            cancel_error=TrinoTransportError("coordinator down"),
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # polling URI_1 so cancel issues a DELETE

        cancelled = await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert cancelled.state == CANCELLED  # DELETE failure is best-effort
        assert record.state == CANCELLED

    asyncio.run(scenario())


def test_cancel_after_finish_raises(store: ExecutionStore) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        with pytest.raises(ValueError):
            await executor.cancel(record.query_execution_id)

    asyncio.run(scenario())


def test_completion_stashes_final_page_on_record(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=None,
                    columns=[
                        TrinoColumn(name="col_a", column_type="varchar"),
                        TrinoColumn(name="col_b", column_type="integer"),
                    ],
                    data=[["alpha", 1], ["beta", 2]],
                    stats={"state": "FINISHED"},
                )
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.result_columns == [
            ("col_a", "varchar"),
            ("col_b", "integer"),
        ]
        assert record.result_rows == [["alpha", 1], ["beta", 2]]

    asyncio.run(scenario())


def test_semaphore_bounds_concurrency(store: ExecutionStore) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        client = GatedStatementClient(gate)
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            max_concurrent_queries=2,
        )
        records = [
            executor.start(query=f"SELECT {i}", workgroup="primary")
            for i in range(4)
        ]
        await asyncio.sleep(0.02)
        assert [record.state for record in records] == [
            RUNNING,
            RUNNING,
            QUEUED,
            QUEUED,
        ]

        gate.set()
        await asyncio.gather(
            *[executor._tasks[r.query_execution_id] for r in records]
        )

        assert client.peak_active <= 2
        assert all(record.state == SUCCEEDED for record in records)

    asyncio.run(scenario())


def test_ensure_query_finished_prefinish_400_parity(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        gate = asyncio.Event()
        client = GatedStatementClient(gate)
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        running = executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)
        assert running.state == RUNNING

        with pytest.raises(InvalidRequestException) as error:
            executor.ensure_query_finished(running.query_execution_id)
        assert (
            str(error.value)
            == "Query has not yet finished. Current state: RUNNING"
        )
        gate.set()
        await executor._tasks[running.query_execution_id]
        assert (
            executor.ensure_query_finished(running.query_execution_id)
            is running
        )

    asyncio.run(scenario())


def test_ensure_query_finished_unknown_execution_raises(
    store: ExecutionStore,
) -> None:
    executor = QueryExecutor(
        store=store,
        client=ScriptedStatementClient([]),
        writer=RecordingWriter(),
    )

    with pytest.raises(InvalidRequestException) as error:
        executor.ensure_query_finished("no-such-execution")

    assert "no-such-execution" in str(error.value)
