"""awswrangler partitioned-read consumer suite.

Drives real awswrangler 3.17.1 against a **partitioned** table through the
emulator (in-process uvicorn) and the compose moto container as the shared
data plane, exactly like the read/write-path suites.

The partitioned-read failure mode (measured 2026-09-24) lives in moto, not here: Trino's
hive connector lists partitions with a blank GetPartitions ``Expression''
(5.1.16 raised ``Unsupported expression ''``) and prunes with the full Hive
type spelling of the partition key (``varchar(2)``/``decimal(10,2)`` →
``Unknown type`` in ``_cast``). The overlay fixes both; this suite pins the
consumer-visible result: a partitioned CTAS registers the ``varchar(2)`` +
``decimal(10,2)`` partition keys, the full read observes all partitions, a
``WHERE``-pruned read observes exactly its partition, and the
``"table$partitions"`` virtual table lists the metastore partitions.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from decimal import Decimal

import awswrangler as wr
import pytest
from botocore.client import BaseClient
from tests.integration._consumer_harness import (
    ConsumerHarness,
    consumer_harness_scope,
)
from tests.integration.conftest import LiveAthenaServer

# (region, amount) tuples every partitioned `sales` view must contain. The
# decimal scale comes from the Trino table schema (10,2), so partition-pruned
# and $partitions reads agree with the parquet data reads.
EXPECTED_SALES = [
    ("EU", Decimal("3.14")),
    ("US", Decimal("3.14")),
    ("US", Decimal("10.50")),
]


@pytest.fixture()
def consumer_harness(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[ConsumerHarness]:
    """Bind wrangler's boto3 session and the emulator to the live stack."""
    with consumer_harness_scope(
        live_athena_server, monkeypatch, "cs2b3"
    ) as harness:
        yield harness


def test_partitioned_ctas_registers_partition_keys_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Trino CTAS registers typed partition keys + values in Glue.

    The partition keys keep their full Hive spelling (``varchar(2)`` and
    ``decimal(10,2)``) so wrangler's ``GetTableMetadata`` dtype table stays
    faithful to real AWS — only moto's filter casting is normalized (the
    overlay), never the registered metadata.
    """
    table_name = _create_partitioned_sales(consumer_harness)

    table = consumer_harness.glue.get_table(
        DatabaseName=consumer_harness.database, Name=table_name
    )["Table"]
    keys = table["PartitionKeys"]
    assert [(key["Name"], key["Type"]) for key in keys] == [
        ("region", "varchar(2)"),
        ("amount", "decimal(10,2)"),
    ]

    response = consumer_harness.glue.get_partitions(
        DatabaseName=consumer_harness.database, TableName=table_name
    )
    # Glue stores partition values in their string spelling; Trino normalizes
    # the decimal strings to their shortest form (10.5), so compare against
    # the numeric amount (the typed reads keep the (10,2) scale: 10.50).
    values = sorted(
        (
            partition["Values"][0],
            Decimal(partition["Values"][1]),
        )
        for partition in response["Partitions"]
    )
    assert values == sorted(EXPECTED_SALES)

    # Trino wrote the partition files into the CTAS external_location.
    listing = consumer_harness.s3.list_objects_v2(
        Bucket=consumer_harness.bucket, Prefix=f"results/{table_name}/"
    )["Contents"]
    prefixes = {item["Key"].split("/")[2] for item in listing}
    assert {"region=EU", "region=US"} <= prefixes


def test_read_sql_query_partitioned_full_read_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """A partition-less read lists every partition (blank Expression).

    The list-all GetPartitions path (previous ``Unsupported expression ''``
    hard-fail) returns all three rows through wrangler's csv read-back.
    """
    table_name = _create_partitioned_sales(consumer_harness)

    frame = wr.athena.read_sql_query(
        sql=f'SELECT * FROM "{consumer_harness.database}"."{table_name}"',
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert _sales_rows(frame) == sorted(EXPECTED_SALES)

    execution = consumer_harness.athena.get_query_execution(
        QueryExecutionId=frame.query_metadata["QueryExecutionId"]
    )["QueryExecution"]
    assert execution["Status"]["State"] == "SUCCEEDED"


def test_read_sql_query_partitioned_pruned_read_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``WHERE region = 'EU'`` prunes via the ``varchar(2)`` cast.

    Trino translates the predicate into a Glue filter expression and moto
    casts the ``EU`` literal with the key's full type — the exact
    ``Unknown type : 'varchar(2)'`` path that hard-failed before the overlay.
    """
    table_name = _create_partitioned_sales(consumer_harness)

    frame = wr.athena.read_sql_query(
        sql=(
            f'SELECT * FROM "{consumer_harness.database}"."{table_name}" '
            "WHERE region = 'EU'"
        ),
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert _sales_rows(frame) == [("EU", Decimal("3.14"))]

    execution = consumer_harness.athena.get_query_execution(
        QueryExecutionId=frame.query_metadata["QueryExecutionId"]
    )["QueryExecution"]
    assert "WHERE region = 'EU'" in execution["Query"]
    assert execution["Status"]["State"] == "SUCCEEDED"


def test_read_sql_query_partitioned_decimal_pruned_read_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``WHERE amount = 10.5`` prunes via the ``decimal(10,2)`` cast."""
    table_name = _create_partitioned_sales(consumer_harness)

    frame = wr.athena.read_sql_query(
        sql=(
            f'SELECT * FROM "{consumer_harness.database}"."{table_name}" '
            "WHERE amount = 10.5"
        ),
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert _sales_rows(frame) == [("US", Decimal("10.50"))]
    assert str(frame["amount"].iloc[0]) == "10.50"


def test_sales_partitions_virtual_table_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``"table$partitions"`` lists the metastore partitions.

    The Hive connector's ``$partitions`` virtual table lists partitions with a
    blank GetPartitions Expression (Trino 483 has no ``SHOW PARTITIONS``), so
    its success is the list-all fix surfacing through the metastore values.
    """
    table_name = _create_partitioned_sales(consumer_harness)

    frame = wr.athena.read_sql_query(
        sql=(
            "SELECT region, amount FROM "
            f'"{consumer_harness.database}"."{table_name}$partitions"'
        ),
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert _sales_rows(frame) == sorted(EXPECTED_SALES)


def test_show_partitions_athena_spelling_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``SHOW PARTITIONS <t>`` (Athena spelling) lists the partition rows.

    Trino 483 has no ``SHOW PARTITIONS`` grammar — the coordinator rejects
    ``PARTITIONS`` after ``SHOW`` outright — so the emulator's dialect map
    reads the Hive connector's ``<t>$partitions`` system table. The wire
    rows are columnar (one column per partition key) where real Athena
    renders ``key=value`` strings — the shape-vs-content delta AWS's own
    SHOW PARTITIONS docs accept by naming ``$partitions`` the equivalent.
    """
    table_name = _create_partitioned_sales(consumer_harness)

    query_id = consumer_harness.athena.start_query_execution(
        QueryString=f"SHOW PARTITIONS {table_name}",
        QueryExecutionContext={"Database": consumer_harness.database},
        ResultConfiguration={"OutputLocation": consumer_harness.prefix},
        WorkGroup="primary",
    )["QueryExecutionId"]
    _wait_for_succeeded(consumer_harness.athena, query_id)

    rows = consumer_harness.athena.get_query_results(
        QueryExecutionId=query_id
    )["ResultSet"]["Rows"]
    cells = [
        [
            cell["VarCharValue"]
            for cell in row["Data"]
            if "VarCharValue" in cell
        ]
        for row in rows[1:]
    ]
    values = sorted((region, Decimal(amount)) for region, amount in cells)
    assert values == sorted(EXPECTED_SALES)


def test_repair_table_discovers_stray_partition_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``repair_table`` registers a partition Glue never saw.

    wrangler submits ``MSCK REPAIR TABLE `t`;`` with a backticked Database
    context (awswrangler/athena/_utils.py:581) — Hive vocabulary Trino's
    grammar rejects; the emulator's dialect map submits
    ``CALL system.sync_partition_metadata(schema, table, 'ADD')`` instead
    (trino.io hive connector procedures). A stray parquet under a new
    ``region=XX/amount=9.99/`` prefix is unregistered until the repair runs;
    the Glue catalog afterwards proves discovery, not just SUCCEEDED.
    """
    table_name = _create_partitioned_sales(consumer_harness)

    source_key = consumer_harness.s3.list_objects_v2(
        Bucket=consumer_harness.bucket, Prefix=f"results/{table_name}/"
    )["Contents"][0]["Key"]
    consumer_harness.s3.copy_object(
        Bucket=consumer_harness.bucket,
        Key=f"results/{table_name}/region=XX/amount=9.99/stray.parquet",
        CopySource=f"{consumer_harness.bucket}/{source_key}",
    )

    state = wr.athena.repair_table(
        table=table_name,
        database=consumer_harness.database,
        s3_output=consumer_harness.prefix,
    )
    assert state == "SUCCEEDED"

    partitions = consumer_harness.glue.get_partitions(
        DatabaseName=consumer_harness.database, TableName=table_name
    )["Partitions"]
    values = sorted(
        (partition["Values"][0], Decimal(partition["Values"][1]))
        for partition in partitions
    )
    assert values == sorted([*EXPECTED_SALES, ("XX", Decimal("9.99"))])


def test_describe_and_show_create_table_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``describe_table``/``show_create_table`` read Athena-shaped results.

    wrangler submits ``DESCRIBE `t`;`` / ``SHOW CREATE TABLE `t`;`` with a
    backticked Database context (awswrangler/athena/_utils.py:659-661,
    :988-990); the emulator maps the statement to Trino quoting and reshapes
    Trino's DESCRIBE result into Athena's col_name/data_type/comment with
    the '# Partition Information' block the parser's Partition flags need
    (_utils.py:224-239, :1011).
    """
    table_name = _create_partitioned_sales(consumer_harness)

    described = wr.athena.describe_table(
        table=table_name,
        database=consumer_harness.database,
        s3_output=consumer_harness.prefix,
    )
    assert described["Column Name"].tolist() == [
        "quantity",
        "region",
        "amount",
    ]
    assert described["Partition"].tolist() == [False, True, True]

    ddl = wr.athena.show_create_table(
        table=table_name,
        database=consumer_harness.database,
        s3_output=consumer_harness.prefix,
    )
    assert ddl.startswith("CREATE TABLE")
    assert table_name in ddl


def _create_partitioned_sales(consumer_harness: ConsumerHarness) -> str:
    """CTAS a region/amount-partitioned ``sales`` table on Trino (setup)."""
    table_name = f"sales_{uuid.uuid4().hex[:6]}"
    location = f"{consumer_harness.prefix}{table_name}"
    query_id = consumer_harness.athena.start_query_execution(
        QueryString=(
            f"CREATE TABLE {consumer_harness.database}.{table_name} "
            "WITH (format = 'PARQUET', "
            f"external_location = '{location}', "
            "partitioned_by = ARRAY['region', 'amount']) AS "
            "SELECT * FROM (VALUES "
            "(3, CAST('US' AS VARCHAR(2)), CAST(10.50 AS DECIMAL(10, 2))), "
            "(7, CAST('EU' AS VARCHAR(2)), CAST(3.14 AS DECIMAL(10, 2))), "
            "(5, CAST('US' AS VARCHAR(2)), CAST(3.14 AS DECIMAL(10, 2)))"
            ") AS t(quantity, region, amount)"
        ),
        QueryExecutionContext={"Database": consumer_harness.database},
        ResultConfiguration={"OutputLocation": consumer_harness.prefix},
        WorkGroup="primary",
    )["QueryExecutionId"]
    _wait_for_succeeded(consumer_harness.athena, query_id)
    return table_name


def _wait_for_succeeded(athena: BaseClient, query_id: str) -> None:
    """Block until the execution reaches SUCCEEDED, raising its reason on FAILED."""
    for _ in range(120):
        execution = athena.get_query_execution(QueryExecutionId=query_id)[
            "QueryExecution"
        ]
        state = execution["Status"]["State"]
        if state == "SUCCEEDED":
            return
        if state == "FAILED":
            reason = execution["Status"].get("StateChangeReason")
            raise AssertionError(f"execution {query_id} FAILED: {reason}")
        time.sleep(0.5)
    raise AssertionError(f"execution {query_id} did not finish within 60s")


def _sales_rows(frame) -> list[tuple[str, Decimal]]:
    """The (region, amount) rows of a read frame, sorted for stability."""
    return sorted(
        (str(region), Decimal(str(amount)))
        for region, amount in zip(
            frame["region"], frame["amount"], strict=True
        )
    )
