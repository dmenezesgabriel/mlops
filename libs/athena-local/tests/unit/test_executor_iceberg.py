"""Iceberg statement routing through the executor.

A static probe drives the catalog qualification: TBLPROPERTIES-declared
CREATEs and Glue-registered Iceberg references submit against the dedicated
``iceberg`` catalog while Hive references stay session-relative.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.executions import (
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.submission import TRINO_CATALOG, TRINO_USER
from athena_local.trino_client import (
    TrinoColumn,
)
from tests.unit._executor_fakes import (
    URI_1,
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)
from tests.unit._iceberg_fakes import StaticIcebergProbe


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_iceberg_create_submits_against_the_dedicated_catalog(
    store: ExecutionStore,
) -> None:
    """TBLPROPERTIES('table_type'='ICEBERG') maps to the iceberg catalog's
    CREATE; the record still carries the Athena statement as submitted."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1), result_page(next_uri=None)]
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=writer,
            iceberg_probe=StaticIcebergProbe(set()),
        )
        record = await executor.start(
            query=(
                "CREATE TABLE `ice_t` (`id` bigint, `v` string) "
                "LOCATION 's3://b/ice_t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG')"
            ),
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                'CREATE TABLE iceberg."analytics"."ice_t" '
                '("id" bigint, "v" varchar) '
                "WITH (format='PARQUET', location='s3://b/ice_t/')",
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.state == SUCCEEDED
        assert record.query.startswith("CREATE TABLE `ice_t`")

    asyncio.run(scenario())


def test_iceberg_merge_routes_only_the_iceberg_reference(
    store: ExecutionStore,
) -> None:
    """MERGE onto a Glue table_type=ICEBERG target is catalog-qualified while
    the hive staging table stays session-catalog relative."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=URI_1), result_page(next_uri=None)]
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=writer,
            iceberg_probe=StaticIcebergProbe({("analytics", "ice_t")}),
        )
        record = await executor.start(
            query=(
                'MERGE INTO "analytics"."ice_t" target '
                'USING "analytics"."temp_table_x" source '
                'ON target."id" = source."id" WHEN MATCHED THEN DELETE'
            ),
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                'MERGE INTO iceberg."analytics"."ice_t" target '
                'USING "analytics"."temp_table_x" source '
                'ON target."id" = source."id" WHEN MATCHED THEN DELETE',
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.state == SUCCEEDED

    asyncio.run(scenario())


def test_hive_statement_is_untouched_when_probe_finds_no_iceberg(
    store: ExecutionStore,
) -> None:
    """A SELECT over non-Iceberg tables submits verbatim (dialect only)."""
    writer = RecordingWriter()

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=URI_1,
                    columns=[TrinoColumn(name="n", column_type="bigint")],
                    data=[[1]],
                ),
                result_page(next_uri=None),
            ]
        )
        executor = QueryExecutor(
            store=store,
            client=client,
            writer=writer,
            iceberg_probe=StaticIcebergProbe(set()),
        )
        record = await executor.start(
            query='SELECT * FROM "analytics"."plain_t"',
            workgroup="primary",
            database="analytics",
        )
        await executor._tasks[record.query_execution_id]

        assert client.submissions == [
            (
                'SELECT * FROM "analytics"."plain_t"',
                TRINO_CATALOG,
                "analytics",
                TRINO_USER,
            )
        ]
        assert record.state == SUCCEEDED

    asyncio.run(scenario())
