"""CREATE EXTERNAL TABLE consumer suite.

Athena's Hive-style ``CREATE EXTERNAL TABLE … STORED AS … LOCATION`` DDL —
the shape awswrangler's ``generate_create_query`` emits
(``awswrangler/athena/_utils.py:1076``) — has no Trino 483 grammar, so the
emulator's dialect map submits ``CREATE TABLE … WITH (format,
external_location[, partitioned_by])`` instead (external_table.py). These
tests pin the consumer-visible result on the live stack: the staged parquet
reads back through the Athena wire, a ``PARTITIONED BY`` declaration
survives into MSCK discovery, and AWS-valid-but-unmappable clauses return
the shaped ``InvalidRequestException`` AWS uses for rejected DDL.
"""

from __future__ import annotations

import io
import time
import uuid
from collections.abc import Iterator

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from botocore.client import BaseClient
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
        live_athena_server, monkeypatch, "extddl"
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


def _run_ddl(harness: ConsumerHarness, query: str) -> str:
    query_id = harness.athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": harness.database},
        ResultConfiguration={"OutputLocation": harness.prefix},
        WorkGroup="primary",
    )["QueryExecutionId"]
    _wait_for_succeeded(harness.athena, query_id)
    return query_id


def _result_cells(harness: ConsumerHarness, query_id: str) -> list[list[str]]:
    rows = harness.athena.get_query_results(QueryExecutionId=query_id)[
        "ResultSet"
    ]["Rows"]
    return [
        [cell.get("VarCharValue", "") for cell in row["Data"]]
        for row in rows[1:]
    ]


def _wait_for_succeeded(athena: BaseClient, query_id: str) -> None:
    """Block until SUCCEEDED, raising the reason on FAILED."""
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


def test_create_external_table_reads_staged_parquet_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """The minimal awswrangler probe shape registers a readable table.

    ``CREATE EXTERNAL TABLE t (id bigint, item string) STORED AS PARQUET
    LOCATION 's3://…'`` → Trino ``CREATE TABLE … WITH (format='PARQUET',
    external_location=…)``; the Hive ``string`` type arrives as Trino
    ``varchar`` and the Glue entry carries ``EXTERNAL_TABLE`` semantics.
    """
    table_name = f"ext_{uuid.uuid4().hex[:6]}"
    location = _stage_parquet(
        consumer_harness,
        f"ext/{table_name}/data.parquet",
        {"id": [1, 2], "item": ["a", "b"]},
    )

    _run_ddl(
        consumer_harness,
        f"CREATE EXTERNAL TABLE {table_name} (id bigint, item string) "
        f"STORED AS PARQUET LOCATION '{location}'",
    )

    select_id = _run_ddl(
        consumer_harness, f"SELECT id, item FROM {table_name} ORDER BY id"
    )
    assert _result_cells(consumer_harness, select_id) == [
        ["1", "a"],
        ["2", "b"],
    ]

    table = consumer_harness.glue.get_table(
        DatabaseName=consumer_harness.database, Name=table_name
    )["Table"]
    assert table["TableType"] == "EXTERNAL_TABLE"
    assert table["Parameters"]["EXTERNAL"] == "TRUE"
    types = {
        c["Name"]: c["Type"] for c in table["StorageDescriptor"]["Columns"]
    }
    assert types == {"id": "bigint", "item": "string"}


def test_create_external_table_partitioned_repairs_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``PARTITIONED BY`` survives as ``partitioned_by`` through MSCK.

    The Hive ``key=value/`` layout plus ``MSCK REPAIR TABLE`` (already
    dialect-mapped to ``system.sync_partition_metadata``) discovers the
    staged partition the emulator registered at CREATE time.
    """
    table_name = f"extp_{uuid.uuid4().hex[:6]}"
    staged_dir = _stage_parquet(
        consumer_harness,
        f"part/{table_name}/region=EU/data.parquet",
        {"id": [7]},
    )
    # The table LOCATION is the dir ABOVE the region=EU partition dir —
    # sync_partition_metadata scans it for key=value children.
    location = staged_dir.removesuffix("region=EU/")

    _run_ddl(
        consumer_harness,
        f"CREATE EXTERNAL TABLE {table_name} (id bigint) "
        f"PARTITIONED BY (region string) "
        f"STORED AS PARQUET LOCATION '{location}'",
    )
    _run_ddl(consumer_harness, f"MSCK REPAIR TABLE {table_name}")

    select_id = _run_ddl(
        consumer_harness,
        f"SELECT id, region FROM {table_name} ORDER BY id",
    )
    assert _result_cells(consumer_harness, select_id) == [["7", "EU"]]


def test_create_external_table_unmappable_clause_is_shaped_400_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """An AWS-valid ``uniontype`` column rejects at submit, AWS-style.

    ``uniontype`` has no Trino counterpart, so the dialect map raises the
    same ``InvalidRequestException`` shape real Athena returns for DDL it
    cannot execute — naming the offender in the message.
    """
    table_name = f"extbad_{uuid.uuid4().hex[:6]}"
    with pytest.raises(ClientError) as exc_info:
        consumer_harness.athena.start_query_execution(
            QueryString=(
                f"CREATE EXTERNAL TABLE {table_name} "
                "(a uniontype<int,string>) "
                f"STORED AS PARQUET LOCATION '{consumer_harness.prefix}bad/'"
            ),
            QueryExecutionContext={"Database": consumer_harness.database},
            ResultConfiguration={"OutputLocation": consumer_harness.prefix},
            WorkGroup="primary",
        )

    response = exc_info.value.response
    assert response["Error"]["Code"] == "InvalidRequestException"
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "uniontype" in response["Error"]["Message"]
