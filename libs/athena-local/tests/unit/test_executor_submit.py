"""Submit-path behavior of the query executor (ADR-0009 #2).

Manifest snapshot capture ahead of INSERT/UNLOAD submit, failed-statement
resolution starting FAILED without a Trino round-trip, and the Athena→Trino
statement mappings (CREATE DATABASE, MSCK REPAIR TABLE, SHOW PARTITIONS,
CREATE EXTERNAL TABLE, resolved EXECUTE) reaching the wire rewritten while
the record keeps the Athena text.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.executions import (
    FAILED,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.output_targets import ManifestTargetError, OutputSnapshot
from athena_local.statement_classification import StatementClassification
from athena_local.submission import TRINO_CATALOG, TRINO_USER
from tests.unit._executor_fakes import (
    RecordingSnapshotter,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_insert_start_captures_snapshot_before_submit(
    store: ExecutionStore,
) -> None:
    snapshot = OutputSnapshot(
        location="s3://data-bucket/events/",
        before_paths=frozenset({"s3://data-bucket/events/old-0.parquet"}),
    )

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        snapshotter = RecordingSnapshotter(
            snapshot=snapshot, capture_client=client
        )
        writer = RecordingWriter()
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=writer,
            snapshotter=snapshotter,
        )
        classification = StatementClassification("DML", "INSERT")
        record = await executor.start(
            query="INSERT INTO analytics.events SELECT 1",
            workgroup="primary",
            database="analytics",
            statement_classification=classification,
        )
        await executor._tasks[record.query_execution_id]

        # Capture ran pre-submit and the writer received the snapshot for its
        # diff; the record itself no longer holds the (possibly large) key set.
        assert snapshotter.calls == [
            ("INSERT INTO analytics.events SELECT 1", "INSERT")
        ]
        assert writer.snapshots == [snapshot]
        assert record.output_snapshot is None
        assert record.manifest_target_error is None
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_terminal_execution_releases_the_manifest_snapshot(
    store: ExecutionStore,
) -> None:
    """The pre-submit snapshot is in-flight only; a terminal record drops it.

    Retaining the captured key set for the record's TTL measured ~1 GB at the
    store cap (methodology.md §6); the artifact write, which runs before the
    terminal transition, is its only consumer.
    """

    snapshot = OutputSnapshot(
        location="s3://data-bucket/events/",
        before_paths=frozenset(
            f"s3://data-bucket/events/old-{index}.parquet"
            for index in range(3)
        ),
    )

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        snapshotter = RecordingSnapshotter(snapshot=snapshot)
        writer = RecordingWriter()
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=writer,
            snapshotter=snapshotter,
        )
        record = await executor.start(
            query="INSERT INTO analytics.events SELECT 1",
            workgroup="primary",
            statement_classification=StatementClassification("DML", "INSERT"),
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert writer.snapshots == [snapshot]
        assert record.output_snapshot is None

    asyncio.run(scenario())


def test_insert_unresolvable_target_marks_the_record(
    store: ExecutionStore,
) -> None:
    error = ManifestTargetError(
        "INSERT target table analytics.missing does not exist in the catalogue"
    )

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        snapshotter = RecordingSnapshotter(outcome=error)
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        classification = StatementClassification("DML", "INSERT")
        record = await executor.start(
            query="INSERT INTO analytics.missing SELECT 1",
            workgroup="primary",
            statement_classification=classification,
        )
        await executor._tasks[record.query_execution_id]

        # Capture leaves a reason instead of failing submit, so Trino's own
        # analysis error surfaces first when the target truly is missing.
        assert record.output_snapshot is None
        assert record.manifest_target_error == str(error)

    asyncio.run(scenario())


def test_non_insert_statements_skip_the_snapshotter(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=None), result_page(next_uri=None)]
        )
        snapshotter = RecordingSnapshotter(
            snapshot=OutputSnapshot(
                location="s3://ctas-bucket/t1/",
                before_paths=frozenset(),
            )
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        select_record = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            statement_classification=StatementClassification("DML", "SELECT"),
        )
        await executor._tasks[select_record.query_execution_id]
        ctas_record = await executor.start(
            query="CREATE TABLE t AS SELECT 1 AS a",
            workgroup="primary",
            statement_classification=StatementClassification(
                "DDL", "CREATE_TABLE_AS_SELECT"
            ),
        )
        await executor._tasks[ctas_record.query_execution_id]

        assert snapshotter.calls == []
        assert select_record.output_snapshot is None
        assert ctas_record.output_snapshot is None
        assert select_record.manifest_target_error is None

    asyncio.run(scenario())


def test_insert_without_snapshotter_flags_the_record(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        classification = StatementClassification("DML", "INSERT")
        record = await executor.start(
            query="INSERT INTO analytics.events SELECT 1",
            workgroup="primary",
            statement_classification=classification,
        )
        await executor._tasks[record.query_execution_id]

        assert record.output_snapshot is None
        assert record.manifest_target_error == (
            "no manifest snapshotter configured for INSERT statements"
        )

    asyncio.run(scenario())


def test_start_skips_trino_and_fails_on_resolution_failure(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        reason = "PreparedStatement st was not found in workGroup primary"
        record = await executor.start(
            query='EXECUTE "st"',
            workgroup="primary",
            statement_classification=StatementClassification(
                "UTILITY", "EXECUTE"
            ),
            resolution_failure_reason=reason,
        )

        # Real Athena fails such EXECUTEs — no Trino contact, no artifact
        # work, immediate terminal state.
        assert record.state == FAILED
        assert record.state_change_reason == reason
        assert record.query == 'EXECUTE "st"'
        assert record.statement_type == "UTILITY"
        assert record.resolved_statement is None
        assert client.submissions == []
        assert record.query_execution_id not in executor._tasks

    asyncio.run(scenario())


def test_start_submits_dialect_mapped_create_database(
    store: ExecutionStore,
) -> None:
    """CREATE DATABASE reaches Trino as CREATE SCHEMA; the record keeps the
    original Athena text (dialect.py)."""

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query="create database if not exists newdb",
            workgroup="primary",
            statement_classification=StatementClassification(
                "DDL", "CREATE_DATABASE"
            ),
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                "create schema if not exists newdb",
                TRINO_CATALOG,
                "",
                TRINO_USER,
            )
        ]
        assert record.query == "create database if not exists newdb"
        assert record.statement_type == "DDL"
        assert record.substatement_type == "CREATE_DATABASE"
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_start_submits_msck_as_sync_partition_metadata(
    store: ExecutionStore,
) -> None:
    """MSCK REPAIR TABLE reaches Trino as CALL system.sync_partition_metadata
    with the request's Database context as the schema; the record keeps the
    original Athena text (dialect.py)."""

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query="MSCK REPAIR TABLE `sales`;",
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                "CALL system.sync_partition_metadata("
                "'analytics','sales','ADD')",
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.query == "MSCK REPAIR TABLE `sales`;"
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_start_submits_show_partitions_as_partitions_read(
    store: ExecutionStore,
) -> None:
    """SHOW PARTITIONS reaches Trino as a ``"t$partitions"`` SELECT with the
    request's Database context as the schema; the record keeps the original
    Athena text (dialect.py)."""

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query="SHOW PARTITIONS `sales`;",
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                'SELECT * FROM "analytics"."sales$partitions"',
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.query == "SHOW PARTITIONS `sales`;"
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_start_submits_external_table_as_create_table_with(
    store: ExecutionStore,
) -> None:
    """CREATE EXTERNAL TABLE reaches Trino as CREATE TABLE … WITH(…) with
    the request's Database context as the schema and Hive types translated;
    the record keeps the original Athena text (external_table.py)."""

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query="CREATE EXTERNAL TABLE `sales` (id bigint, item string) "
            "STORED AS PARQUET LOCATION 's3://b/x/'",
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                'CREATE TABLE "analytics"."sales" ("id" bigint, "item" '
                "varchar) WITH (format='PARQUET', "
                "external_location='s3://b/x/')",
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.query == (
            "CREATE EXTERNAL TABLE `sales` (id bigint, item string) "
            "STORED AS PARQUET LOCATION 's3://b/x/'"
        )
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_start_submits_resolved_statement_instead_of_query(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        resolved = "SELECT * FROM flights WHERE origin = ('Washington')"
        record = await executor.start(
            query="EXECUTE \"st\" USING 'Washington'",
            workgroup="primary",
            statement_classification=StatementClassification("DML", "SELECT"),
            resolved_statement=resolved,
        )
        await executor._tasks[record.query_execution_id]

        # The bound copy of the stored statement — never the EXECUTE text —
        # goes on the wire, because Trino has no prepared-statement
        # persistence.
        assert client.submissions == [
            (resolved, TRINO_CATALOG, "", TRINO_USER)
        ]
        assert record.query == "EXECUTE \"st\" USING 'Washington'"
        assert record.resolved_statement == resolved
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_insert_execute_captures_manifest_from_resolved_statement(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        snapshotter = RecordingSnapshotter(
            snapshot=OutputSnapshot(
                location="s3://data-bucket/events/",
                before_paths=frozenset(),
            ),
            capture_client=client,
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=RecordingWriter(),
            snapshotter=snapshotter,
        )
        resolved = "INSERT INTO analytics.events VALUES (1), (2)"
        record = await executor.start(
            query="EXECUTE insert_ev",
            workgroup="primary",
            statement_classification=StatementClassification("DML", "INSERT"),
            resolved_statement=resolved,
        )
        await executor._tasks[record.query_execution_id]

        # Manifest capture inspects the resolved statement: the submitted
        # EXECUTE text carries no target table to snapshot.
        assert snapshotter.calls == [
            ("INSERT INTO analytics.events VALUES (1), (2)", "INSERT")
        ]
        assert record.state == SUCCEEDED

    asyncio.run(scenario())
