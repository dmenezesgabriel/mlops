"""Cancellation paths of the query executor (ADR-0009 #5).

Covers the QUEUED-parked-at-semaphore, RUNNING-DELETE, preflight-window and
terminal no-op cases: ``cancel`` transitions the record first, then makes a
best-effort Trino DELETE of the active statement.
"""

from __future__ import annotations

import asyncio
import logging

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
from athena_local.executor import ArtifactWriteError, QueryExecutor
from athena_local.trino_client import (
    TrinoTransportError,
)
from tests.unit._executor_fakes import (
    URI_1,
    URI_2,
    CancellingWriter,
    GatedStatementClient,
    GatedWriter,
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
        # The preflight already POSTed the queued statement (both submits
        # reach Trino before the runner task exists), so cancelling it while
        # it waits at the semaphore must still DELETE the live statement —
        # the record is QUEUED but the engine-side query is not.
        assert client.cancellations == [URI_2]
        gate.set()
        await asyncio.gather(
            executor._tasks[first.query_execution_id],
            executor._tasks[queued.query_execution_id],
        )
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


def test_cancel_during_artifact_write_aborts_the_write(
    store: ExecutionStore,
) -> None:
    """A StopQueryExecution landing inside ``await writer.write`` aborts the
    write instead of dying on an unretrieved CANCELLED→SUCCEEDED ValueError —
    no artifacts land for a CANCELLED record."""

    async def scenario() -> None:
        write_gate = asyncio.Event()
        writer = GatedWriter(write_gate)
        client = ScriptedStatementClient(
            [result_page(next_uri=None, data=[[1]])]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(query="SELECT 1", workgroup="primary")
        task = executor._tasks[record.query_execution_id]
        await asyncio.sleep(
            0.02
        )  # statement finished; the task is parked inside the write

        cancelled = await executor.cancel(record.query_execution_id)
        write_gate.set()
        await task

        assert cancelled.state == CANCELLED
        # The aborted write never produced artifacts for the cancelled record.
        assert writer.calls == []
        assert executor._write_tasks == {}

    asyncio.run(scenario())


def test_completed_write_during_cancel_keeps_record_cancelled(
    store: ExecutionStore,
) -> None:
    """An uninterruptible write that completes with the record already
    CANCELLED must not be resurrected by the trailing SUCCEEDED transition —
    the artifacts exist but the record stays honest."""

    async def scenario() -> None:
        writer = CancellingWriter()
        client = ScriptedStatementClient(
            [result_page(next_uri=None, data=[[1]])]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(query="SELECT 1", workgroup="primary")
        task = executor._tasks[record.query_execution_id]

        await task

        assert writer.calls == ["write:RUNNING"]
        assert record.state == CANCELLED

    asyncio.run(scenario())


def test_artifact_failure_while_cancelled_stays_cancelled(
    store: ExecutionStore,
) -> None:
    """An ArtifactWriteError surfacing after a mid-write cancel must not
    raise CANCELLED→FAILED either — the user's CANCELLED verdict stands."""

    async def scenario() -> None:
        writer = CancellingWriter(
            error=ArtifactWriteError("moto S3 refused put_object")
        )
        client = ScriptedStatementClient(
            [result_page(next_uri=None, data=[[1]])]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(query="SELECT 1", workgroup="primary")
        task = executor._tasks[record.query_execution_id]

        await task

        assert writer.calls == ["write:RUNNING"]
        assert record.state == CANCELLED

    asyncio.run(scenario())


def test_unexpected_task_failure_is_logged(
    store: ExecutionStore, caplog: pytest.LogCaptureFixture
) -> None:
    """A task dying on an unexpected error surfaces through the
    ``athena_local`` log instead of expiring unretrieved in the done
    callback."""
    caplog.set_level(logging.ERROR, logger="athena_local")
    execution_id = ""

    async def scenario() -> None:
        nonlocal execution_id
        gate = asyncio.Event()
        gate.set()
        writer = GatedWriter(gate, error=RuntimeError("writer exploded"))
        client = ScriptedStatementClient(
            [result_page(next_uri=None, data=[[1]])]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(query="SELECT 1", workgroup="primary")
        execution_id = record.query_execution_id
        task = executor._tasks[record.query_execution_id]

        with pytest.raises(RuntimeError, match="writer exploded"):
            await task
        assert executor._tasks == {}

    asyncio.run(scenario())

    assert any(
        execution_id in logged.getMessage() for logged in caplog.records
    )


def test_external_runner_cancel_reraises_and_reaps_quietly(
    store: ExecutionStore, caplog: pytest.LogCaptureFixture
) -> None:
    """A runner cancelled from outside (shutdown) propagates through the
    write guard — the record is untouched because cancelling the task is
    not a user stop — and the reap callback stays silent for it."""
    caplog.set_level(logging.ERROR, logger="athena_local")

    async def scenario() -> None:
        executor = QueryExecutor(
            store=store,
            client=ScriptedStatementClient([result_page(next_uri=None)]),
            writer=GatedWriter(asyncio.Event()),
        )
        record = await executor.start(query="SELECT 1", workgroup="primary")
        task = executor._tasks[record.query_execution_id]
        await asyncio.sleep(0.02)  # parked inside the artifact write

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)  # let the done callback reap

        assert record.state == RUNNING
        assert executor._tasks == {}

    asyncio.run(scenario())

    assert not caplog.records


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
