"""Cancellation paths of the query executor (ADR-0009 #5).

Covers the QUEUED-parked-at-semaphore, RUNNING-DELETE, preflight-window and
terminal no-op cases: ``cancel`` transitions the record first, then makes a
best-effort Trino DELETE of the active statement.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.errors import (
    InvalidRequestException,
)
from athena_local.executions import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.trino_client import (
    TrinoTransportError,
)
from tests.unit._executor_fakes import (
    URI_1,
    URI_2,
    GatedStatementClient,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_cancel_queued_execution_parks_at_the_semaphore(
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
        first = await executor.start(
            query="SELECT biggest", workgroup="primary"
        )
        await asyncio.sleep(
            0.02
        )  # first task now parks inside the poll fetch holding the slot
        queued = await executor.start(
            query="SELECT cancelled", workgroup="primary"
        )
        assert queued.state == QUEUED

        cancelled = await executor.cancel(queued.query_execution_id)

        assert cancelled.state == CANCELLED
        gate.set()
        await asyncio.gather(
            executor._tasks[first.query_execution_id],
            executor._tasks[queued.query_execution_id],
        )
        # Both statements were preflighted (start-time validation touches
        # Trino), but the queued one was never executed: it stays
        # QUEUED at the semaphore and no DELETE is issued for it.
        assert client.submission_count == 2
        assert client.peak_active == 1
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
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # preflight done, now polling URI_2

        cancelled = await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert cancelled.state == CANCELLED
        # The DELETE targets the active nextUri, which after the preflight
        # fetch is URI_2 (the poll cursor handed to the background task).
        assert client.cancellations == [URI_2]
        assert writer.calls == []

    asyncio.run(scenario())


def test_canceled_then_fetch_error_stays_cancelled(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1), result_page(next_uri=URI_2)],
            fetch_delay_seconds=0.05,
            fetch_error=TrinoTransportError("coordinator gone"),
            fetch_error_uri=URI_2,
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # actively waiting on fetch_next(URI_2)

        await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert record.state == CANCELLED  # transport error must not win

    asyncio.run(scenario())


def test_cancel_during_preflight_execution_does_not_exist(
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
        start_task = asyncio.create_task(
            executor.start(query="SELECT 1", workgroup="primary")
        )
        await asyncio.sleep(
            0.02
        )  # still inside the submit_statement preflight

        # The execution does not exist until the preflight returns, so a
        # concurrent StopQueryExecution answers the shaped "does not exist"
        # and never issues a Trino DELETE.
        with pytest.raises(InvalidRequestException, match="does not exist"):
            await executor.cancel("not-yet-created")

        start_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await start_task
        assert client.cancellations == []

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
        record = await executor.start(query="SELECT 1", workgroup="primary")
        await asyncio.sleep(0.02)  # polling URI_2 so cancel issues a DELETE

        cancelled = await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert cancelled.state == CANCELLED  # DELETE failure is best-effort
        assert record.state == CANCELLED

    asyncio.run(scenario())


@pytest.mark.parametrize("terminal_state", [SUCCEEDED, FAILED, CANCELLED])
def test_cancel_on_terminal_execution_is_a_no_op(
    store: ExecutionStore, terminal_state: str
) -> None:
    """A terminal stop is the modeled idempotent no-op, not a transition.

    The canonical model marks StopQueryExecution idempotent
    (service-2.json): stopping a finished execution changes no state and
    issues no Trino DELETE.
    """

    async def scenario() -> None:
        client = ScriptedStatementClient([])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = store.create(query="SELECT 1", workgroup="primary")
        record.transition_to(RUNNING)
        record.transition_to(terminal_state)

        stopped = await executor.cancel(record.query_execution_id)

        assert stopped is record
        assert record.state == terminal_state
        assert client.cancellations == []

    asyncio.run(scenario())
