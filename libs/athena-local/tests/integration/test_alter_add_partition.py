"""ALTER TABLE … ADD PARTITION consumer suite.

Athena's ``ALTER TABLE t ADD [IF NOT EXISTS] PARTITION (col='v') [LOCATION
's3://…']`` has no Trino 483 grammar; the emulator rewrites it to the Hive
connector's ``CALL system.register_partition(schema, table,
partition_columns, partition_values[, location])`` (partition_alter.py),
which ``hive.allow-register-partition-procedure`` enables in the catalog.
These tests pin the consumer-visible result on the live stack: the staged
partition registers in Glue, ``IF NOT EXISTS`` is the documented no-op on a
registered partition, and the unguarded add keeps AWS's duplicate failure.
"""

from __future__ import annotations

import io
import time
import uuid
from collections.abc import Iterator

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from botocore.exceptions import ClientError
from tests.integration._consumer_harness import (
    ConsumerHarness,
    consumer_harness_scope,
)
from tests.integration.conftest import LiveAthenaServer


@pytest.fixture()
def consumer_harness(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[ConsumerHarness]:
    """Bind the emulator to the live stack with a throwaway bucket/db."""
    with consumer_harness_scope(
        live_athena_server, monkeypatch, "addpart"
    ) as harness:
        yield harness


def _stage_parquet(
    harness: ConsumerHarness, key: str, columns: dict[str, list[object]]
) -> str:
    """Write one parquet file under ``key``; return the s3 dir URL."""
    buffer = io.BytesIO()
    pq.write_table(pa.table(columns), buffer)
    harness.s3.put_object(
        Bucket=harness.bucket, Key=key, Body=buffer.getvalue()
    )
    return f"s3://{harness.bucket}/{key.rsplit('/', 1)[0]}/"


def _start(harness: ConsumerHarness, query: str, **context: str) -> str:
    return harness.athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={
            "Database": harness.database,
            **context,
        },
        ResultConfiguration={"OutputLocation": harness.prefix},
        WorkGroup="primary",
    )["QueryExecutionId"]


def _wait_terminal(harness: ConsumerHarness, query_id: str) -> dict:
    """Block until a terminal state; return the execution."""
    for _ in range(120):
        execution = harness.athena.get_query_execution(
            QueryExecutionId=query_id
        )["QueryExecution"]
        if execution["Status"]["State"] in (
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
        ):
            return execution
        time.sleep(0.5)
    raise AssertionError(f"execution {query_id} did not finish within 60s")


def _create_partitioned_table(harness: ConsumerHarness, table: str) -> str:
    """A ``PARTITIONED BY (region string)`` external table; returns its LOCATION."""
    location = _stage_parquet(
        harness, f"data/{table}/region=EU/seed.parquet", {"id": [1]}
    ).removesuffix("region=EU/")
    query_id = _start(
        harness,
        f"CREATE EXTERNAL TABLE {table} (id bigint) "
        f"PARTITIONED BY (region string) "
        f"STORED AS PARQUET LOCATION '{location}'",
    )
    execution = _wait_terminal(harness, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED", execution["Status"]
    return location


def _partition_values(harness: ConsumerHarness, table: str) -> list[list[str]]:
    response = harness.glue.get_partitions(
        DatabaseName=harness.database, TableName=table
    )
    return [p["Values"] for p in response["Partitions"]]


def test_add_partition_registers_the_staged_location_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """The nb05 probe shape: staged parquet + ADD IF NOT EXISTS … LOCATION
    → SUCCEEDED and the partition is visible in the Glue catalog."""
    table = f"addp_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)
    ap_dir = _stage_parquet(
        consumer_harness,
        f"data/{table}/region=AP/part-0.parquet",
        {"id": [5]},
    )

    query_id = _start(
        consumer_harness,
        f"ALTER TABLE {table} ADD IF NOT EXISTS "
        f"PARTITION (region='AP') LOCATION '{ap_dir}'",
    )

    execution = _wait_terminal(consumer_harness, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED", execution["Status"]
    assert ["AP"] in _partition_values(consumer_harness, table)


def test_add_partition_if_not_exists_repeats_as_a_noop_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Re-adding a registered partition with IF NOT EXISTS SUCCEEDS and
    keeps the original registration — AWS's documented no-op."""
    table = f"addi_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)
    ap_dir = _stage_parquet(
        consumer_harness,
        f"data/{table}/region=AP/part-0.parquet",
        {"id": [5]},
    )
    statement = (
        f"ALTER TABLE {table} ADD IF NOT EXISTS "
        f"PARTITION (region='AP') LOCATION '{ap_dir}'"
    )
    _wait_terminal(consumer_harness, _start(consumer_harness, statement))

    query_id = _start(consumer_harness, statement)

    execution = _wait_terminal(consumer_harness, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED", execution["Status"]
    partitions = consumer_harness.glue.get_partitions(
        DatabaseName=consumer_harness.database, TableName=table
    )["Partitions"]
    locations = {
        tuple(p["Values"]): p["StorageDescriptor"]["Location"]
        for p in partitions
    }
    assert locations[("AP",)].rstrip("/") == ap_dir.rstrip("/")


def test_add_partition_without_guard_fails_on_duplicate_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """The unguarded add keeps AWS's duplicate-partition failure."""
    table = f"addd_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)
    ap_dir = _stage_parquet(
        consumer_harness,
        f"data/{table}/region=AP/part-0.parquet",
        {"id": [5]},
    )
    statement = (
        f"ALTER TABLE {table} ADD PARTITION (region='AP') LOCATION '{ap_dir}'"
    )
    _wait_terminal(consumer_harness, _start(consumer_harness, statement))

    query_id = _start(consumer_harness, statement)

    execution = _wait_terminal(consumer_harness, query_id)
    assert execution["Status"]["State"] == "FAILED"
    assert "already registered" in execution["Status"]["StateChangeReason"]


def test_add_partition_without_location_uses_table_root_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Omitted LOCATION registers the hive-layout dir under the table's
    location — the procedure's (and AWS's) documented default."""
    table = f"addl_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)
    _stage_parquet(
        consumer_harness,
        f"data/{table}/region=AP/part-0.parquet",
        {"id": [5]},
    )

    query_id = _start(
        consumer_harness,
        f"ALTER TABLE {table} ADD PARTITION (region='AP')",
    )

    execution = _wait_terminal(consumer_harness, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED", execution["Status"]
    assert ["AP"] in _partition_values(consumer_harness, table)


def test_add_partition_qualified_backticked_target_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``ALTER TABLE `db`.`t` ADD …`` resolves the qualified schema itself."""
    table = f"addq_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)
    ap_dir = _stage_parquet(
        consumer_harness,
        f"data/{table}/region=AP/part-0.parquet",
        {"id": [5]},
    )

    query_id = _start(
        consumer_harness,
        f"ALTER TABLE `{consumer_harness.database}`.`{table}` "
        f"ADD PARTITION (region='AP') LOCATION '{ap_dir}'",
    )

    execution = _wait_terminal(consumer_harness, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED", execution["Status"]
    assert ["AP"] in _partition_values(consumer_harness, table)


def test_add_partition_without_database_context_is_submit_400_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """An unqualified target with no Database context can't resolve the
    procedure's schema argument — pass-through for Trino's own reject."""
    table = f"addn_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)

    with pytest.raises(ClientError) as exc_info:
        consumer_harness.athena.start_query_execution(
            QueryString=f"ALTER TABLE {table} ADD PARTITION (region='AP')",
            ResultConfiguration={"OutputLocation": consumer_harness.prefix},
            WorkGroup="primary",
        )

    assert (
        exc_info.value.response["Error"]["Code"] == "InvalidRequestException"
    )
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400


def test_add_partition_multi_clause_is_shaped_400_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """AWS accepts multi-PARTITION adds; one Trino statement registers one
    partition, so the emulator rejects at submit naming the limitation."""
    table = f"addm_{uuid.uuid4().hex[:6]}"
    _create_partitioned_table(consumer_harness, table)

    with pytest.raises(ClientError) as exc_info:
        consumer_harness.athena.start_query_execution(
            QueryString=(
                f"ALTER TABLE {table} ADD PARTITION (region='AP') "
                "PARTITION (region='SA')"
            ),
            QueryExecutionContext={"Database": consumer_harness.database},
            ResultConfiguration={"OutputLocation": consumer_harness.prefix},
            WorkGroup="primary",
        )

    response = exc_info.value.response
    assert response["Error"]["Code"] == "InvalidRequestException"
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "PARTITION" in response["Error"]["Message"]
