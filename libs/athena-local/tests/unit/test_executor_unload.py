"""UNLOAD and ADD PARTITION statements through the executor.

UNLOAD maps to a CTAS plus session properties and must drop its transient
catalog table on every exit — success, engine error, cancel-before-poll and
cancel-while-parked; ALTER TABLE ADD PARTITION maps to
``system.register_partition`` with ``IF NOT EXISTS`` tolerating
ALREADY_EXISTS.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.errors import (
    InternalServerException,
)
from athena_local.executions import (
    CANCELLED,
    FAILED,
    QUEUED,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.output_targets import OutputSnapshot
from athena_local.statement_classification import StatementClassification
from athena_local.submission import TRINO_CATALOG, TRINO_USER
from athena_local.trino_client import (
    TrinoQueryError,
)
from tests.unit._executor_fakes import (
    URI_1,
    URI_2,
    GatedStatementClient,
    RecordingSnapshotter,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)

UNLOAD_QUERY = (
    "UNLOAD (SELECT * FROM sales) TO 's3://unload-bucket/out/' "
    "WITH (format='PARQUET')"
)
UNLOAD_CLASSIFICATION = StatementClassification("DML", "UNLOAD")


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_unload_submits_a_ctas_and_drops_the_temp_table(
    store: ExecutionStore,
) -> None:
    """The wire UNLOAD runs as CTAS at the TO path; its Glue entry is dropped.

    Trino's grammar has no UNLOAD, so ``dialect.py`` maps it to a CTAS
    writing the ``TO`` location through a generated temp table — which the
    cleanup then removes from the catalog, because real UNLOAD registers
    nothing.
    """
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1, stats={"state": "RUNNING"}),
                result_page(
                    next_uri=None, update_type="CREATE TABLE AS SELECT"
                ),
            ]
        )
        snapshotter = RecordingSnapshotter(
            snapshot=OutputSnapshot(
                location="s3://unload-bucket/out/", before_paths=frozenset()
            ),
            capture_client=client,
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=writer,
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]

        submitted = client.submissions[0][0]
        assert submitted.startswith('CREATE TABLE "analytics"."athena_unload_')
        assert "external_location='s3://unload-bucket/out/'" in submitted
        assert submitted.endswith("AS SELECT * FROM sales")
        # The manifest capture saw the original UNLOAD text — the rewrite
        # consumes the very TO clause ``unload_location`` looks for.
        assert snapshotter.calls == [(UNLOAD_QUERY, "UNLOAD")]
        assert record.query == UNLOAD_QUERY
        assert record.unload_cleanup_table is not None
        assert snapshotter.drop_calls == [record.unload_cleanup_table]
        assert record.state == SUCCEEDED

    asyncio.run(scenario())
    assert writer.calls == ["write:RUNNING"]


def test_unload_compression_reaches_trino_as_a_session_property(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(next_uri=None, update_type="CREATE TABLE"),
            ]
        )
        snapshotter = RecordingSnapshotter()
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query=(
                "UNLOAD (SELECT 1) TO 's3://b/o/' "
                "WITH (format='PARQUET', compression='snappy')"
            ),
            workgroup="primary",
            database="db",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]

        assert client.session_properties_calls == [
            {"hive.compression_codec": "SNAPPY"}
        ]
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_unload_drop_failure_fails_the_execution(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(next_uri=None, update_type="CREATE TABLE"),
            ]
        )
        snapshotter = RecordingSnapshotter(
            drop_error=InternalServerException("glue unreachable")
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]

        # Consumers must not see SUCCEEDED over a deviating catalog state —
        # the leftover temp table would be visible to SHOW TABLES.
        assert record.state == FAILED
        assert "unload" in record.state_change_reason.lower()

    asyncio.run(scenario())


def test_unload_statement_error_still_drops_the_temp_table(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(
                    next_uri=None,
                    error=TrinoQueryError(
                        message="Target directory is not empty",
                        error_type="USER_ERROR",
                        error_name="HIVE_PATH_ALREADY_EXISTS",
                    ),
                ),
            ]
        )
        snapshotter = RecordingSnapshotter()
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        # A failed CTAS may still have registered the temp table — best-effort
        # cleanup keeps the catalog free of emulator litter.
        assert snapshotter.drop_calls == [record.unload_cleanup_table]

    asyncio.run(scenario())


def test_unload_cancel_still_drops_the_temp_table(
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
        )
        snapshotter = RecordingSnapshotter()
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await asyncio.sleep(0.02)  # polling URI_2 so cancel issues a DELETE
        await executor.cancel(record.query_execution_id)
        await executor._tasks[record.query_execution_id]

        assert record.state == CANCELLED
        assert snapshotter.drop_calls == [record.unload_cleanup_table]

    asyncio.run(scenario())


def test_unload_cancel_queued_at_the_semaphore_drops_the_temp_table(
    store: ExecutionStore,
) -> None:
    """A cancel that beats the task's semaphore entry still drops the table.

    The parked CTAS keeps running coordinator-side while the record turns
    CANCELLED; when the task finally enters the semaphore it exits early —
    the drop there is the last cleanup chance before the catalog would show
    an ``athena_unload_*`` residue.
    """

    async def scenario() -> None:
        gate = asyncio.Event()
        client = GatedStatementClient(gate)
        snapshotter = RecordingSnapshotter()
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            max_concurrent_queries=1,
            snapshotter=snapshotter,
        )
        first = await executor.start(
            query="SELECT biggest", workgroup="primary"
        )
        await asyncio.sleep(
            0.02
        )  # first task parked in the poll, holding the slot
        queued = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        assert queued.state == QUEUED

        await executor.cancel(queued.query_execution_id)

        # The parked CTAS was already submitted at preflight — cancelling
        # must DELETE the live statement, not just mark the record.
        assert client.cancellations == [URI_2]
        gate.set()
        await asyncio.gather(
            executor._tasks[first.query_execution_id],
            executor._tasks[queued.query_execution_id],
        )

        assert queued.state == CANCELLED
        assert snapshotter.drop_calls == [queued.unload_cleanup_table]

    asyncio.run(scenario())


def test_unload_without_snapshotter_fails_before_artifacts(
    store: ExecutionStore,
) -> None:
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(next_uri=None, update_type="CREATE TABLE"),
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=writer, snapshotter=None
        )
        record = await executor.start(
            query=UNLOAD_QUERY,
            workgroup="primary",
            database="analytics",
            statement_classification=UNLOAD_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert "unload" in record.state_change_reason.lower()

    asyncio.run(scenario())
    assert writer.calls == []


ADD_PARTITION_QUERY = (
    "ALTER TABLE sales ADD PARTITION (region='AP') LOCATION 's3://b/x/'"
)
ADD_PARTITION_IF_NOT_EXISTS_QUERY = (
    "ALTER TABLE sales ADD IF NOT EXISTS PARTITION (region='AP') "
    "LOCATION 's3://b/x/'"
)


def test_add_partition_submits_the_register_partition_call(
    store: ExecutionStore,
) -> None:
    """Athena's ADD PARTITION reaches Trino as system.register_partition."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1), result_page(next_uri=None)]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(
            query=ADD_PARTITION_QUERY,
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                "CALL system.register_partition('analytics','sales',"
                "ARRAY['region'],ARRAY['AP'],'s3://b/x/')",
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.state == SUCCEEDED
        assert record.partition_noop_on_exists is False

    asyncio.run(scenario())


def test_add_partition_if_not_exists_tolerates_already_exists(
    store: ExecutionStore,
) -> None:
    """An existing partition makes register_partition raise ALREADY_EXISTS;
    with IF NOT EXISTS that is AWS's documented no-op — SUCCEEDED, with the
    old registration kept (the procedure checks before mutating)."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(
                    next_uri=None,
                    error=TrinoQueryError(
                        message="Partition [region=AP] is already registered "
                        "with location s3://b/x/",
                        error_type="USER_ERROR",
                        error_name="ALREADY_EXISTS",
                    ),
                ),
            ]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(
            query=ADD_PARTITION_IF_NOT_EXISTS_QUERY,
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.partition_noop_on_exists is True

    asyncio.run(scenario())
    # The tolerated path still writes result artifacts before SUCCEEDED
    # (ADR-0009 #4) — a no-op ALTER produces them on real Athena too.
    assert writer.calls == ["write:RUNNING"]


def test_add_partition_without_guard_keeps_already_exists_a_failure(
    store: ExecutionStore,
) -> None:
    """Without IF NOT EXISTS real Athena also fails a duplicate add."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=URI_1),
                result_page(
                    next_uri=None,
                    error=TrinoQueryError(
                        message="Partition [region=AP] is already registered "
                        "with location s3://b/x/",
                        error_type="USER_ERROR",
                        error_name="ALREADY_EXISTS",
                    ),
                ),
            ]
        )
        executor = QueryExecutor(store=store, client=client, writer=writer)
        record = await executor.start(
            query=ADD_PARTITION_QUERY,
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == FAILED
        assert "already registered" in record.state_change_reason
        assert record.partition_noop_on_exists is False

    asyncio.run(scenario())
    assert writer.calls == []
