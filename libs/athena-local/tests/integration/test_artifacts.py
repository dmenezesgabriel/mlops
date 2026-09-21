"""AR-1 integration: artifact writers against a live moto S3.

Wrangler-compatible artifact bytes are written through the real project
boundary — ``S3Writer.for_endpoint`` over the ThreadedMotoServer — and read
back with a real boto3 client, so the exact consumer contract (header CSV,
sidecar metadata, CTAS manifest) is pinned at the HTTP boundary with no Trino
needed. The CSV acceptance re-reads the object with pandas using the verbatim
``s3.read_csv`` arguments from ``_fetch_csv_result``
(awswrangler/athena/_read.py:225-238) and asserts the nullable dtypes
round-trip; CS-2 runs the real ``wr.athena.read_sql_query`` path end to end.
Same moto instance serves the seeding writes and the writer's reads, pinning
ADR-0005's single-store guarantee for S3.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import boto3
import pandas as pd
import pytest
from athena_local.artifacts import ArtifactWriter
from athena_local.common_schemas import ResultConfiguration
from athena_local.executions import ExecutionStore, QueryExecutionRecord
from athena_local.s3_writer import S3Writer
from athena_local.trino_client import TrinoPage
from botocore.client import BaseClient
from moto.backends import get_backend
from tests.integration.conftest import LiveMotoServer

PLACEHOLDER_PAGE = TrinoPage(
    query_id="id",  # the writer reads the record's cached columns/rows
    next_uri=None,
    update_type=None,
    columns=[],
    data=[],
    stats={},
    error=None,
)


@dataclass
class ArtifactStack:
    """The live stack: seeding S3 client plus the writer under test."""

    s3: BaseClient
    writer: ArtifactWriter
    results_bucket: str
    ctas_bucket: str

    def object_bytes(self, bucket: str, key: str) -> bytes:
        return self.s3.get_object(Bucket=bucket, Key=key)["Body"].read()


@pytest.fixture()
def artifact_stack(
    live_moto_server: LiveMotoServer,
) -> Iterator[ArtifactStack]:
    # moto backends are process-global: every ThreadedMotoServer shares one S3
    # store, so seeded objects leak between tests unless reset each time.
    get_backend("s3").reset()
    s3 = boto3.client(
        "s3",
        endpoint_url=live_moto_server.url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    results_bucket = f"athena-results-{uuid.uuid4().hex}"
    ctas_bucket = f"athena-ctas-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=results_bucket)
    s3.create_bucket(Bucket=ctas_bucket)
    yield ArtifactStack(
        s3=s3,
        writer=ArtifactWriter(S3Writer.for_endpoint(live_moto_server.url)),
        results_bucket=results_bucket,
        ctas_bucket=ctas_bucket,
    )


def make_record(
    *,
    query: str,
    statement_type: str,
    substatement_type: str,
    output_location: str,
    columns: list[tuple[str, str]] | None = None,
    rows: list[list[object]] | None = None,
) -> QueryExecutionRecord:
    record = ExecutionStore().create(
        query=query,
        workgroup="primary",
        database="analytics",
        result_configuration=ResultConfiguration(
            output_location=output_location
        ),
        statement_type=statement_type,
        substatement_type=substatement_type,
    )
    record.cache_result_page(
        columns if columns is not None else [],
        rows if rows is not None else [],
    )
    return record


def test_select_csv_round_trips_through_moto_s3(
    artifact_stack: ArtifactStack,
) -> None:
    stack = artifact_stack
    output_location = f"s3://{stack.results_bucket}/analytics/"
    record = make_record(
        query="SELECT id, name, ok FROM analytics.t",
        statement_type="DML",
        substatement_type="SELECT",
        output_location=output_location,
        columns=[("id", "integer"), ("name", "varchar"), ("ok", "boolean")],
        rows=[[1, "alpha", True], [None, "beta", False]],
    )

    asyncio.run(stack.writer.write(record, PLACEHOLDER_PAGE))

    query_id = record.query_execution_id
    csv_key = f"analytics/{query_id}.csv"
    metadata_key = f"analytics/{query_id}.csv.metadata"
    assert stack.object_bytes(stack.results_bucket, csv_key) == (
        b'"id","name","ok"\n"1","alpha","True"\n"","beta","False"\n'
    )
    assert json.loads(
        stack.object_bytes(stack.results_bucket, metadata_key).decode("utf-8")
    ) == {
        "columns": [
            {"Name": "id", "Type": "integer"},
            {"Name": "name", "Type": "varchar"},
            {"Name": "ok", "Type": "boolean"},
        ],
        "rows": 2,
    }

    listing = stack.s3.list_objects_v2(
        Bucket=stack.results_bucket, Prefix="analytics/"
    )["Contents"]
    assert sorted(item["Key"] for item in listing) == [csv_key, metadata_key]


def test_csv_matches_wranglers_pandas_read_args(
    artifact_stack: ArtifactStack,
) -> None:
    """The header CSV parsed with _fetch_csv_result's exact args round-trips."""
    stack = artifact_stack
    output_location = f"s3://{stack.results_bucket}/analytics/"
    record = make_record(
        query="SELECT id, name FROM analytics.t",
        statement_type="DML",
        substatement_type="SELECT",
        output_location=output_location,
        columns=[("id", "integer"), ("name", "varchar")],
        rows=[[1, "alpha"], [None, "beta"]],
    )

    asyncio.run(stack.writer.write(record, PLACEHOLDER_PAGE))

    body = stack.object_bytes(
        stack.results_bucket,
        f"analytics/{record.query_execution_id}.csv",
    )
    frame = pd.read_csv(
        io.BytesIO(body),
        dtype={"id": "Int32", "name": "string"},
        parse_dates=[],
        converters={},
        quoting=csv.QUOTE_ALL,
        keep_default_na=False,
        na_values=["", "NaN"],
        skip_blank_lines=False,
    )

    assert list(frame.columns) == ["id", "name"]
    assert str(frame["id"].dtype) == "Int32"
    assert frame["id"].isna().tolist() == [False, True]
    assert frame["id"].dropna().astype(int).tolist() == [1]
    assert frame["name"].tolist() == ["alpha", "beta"]


def test_ctas_manifest_lists_the_created_files(
    artifact_stack: ArtifactStack,
) -> None:
    stack = artifact_stack
    output_location = f"s3://{stack.results_bucket}/analytics/"
    ctas_location = f"s3://{stack.ctas_bucket}/t1/"
    record = make_record(
        query=(
            'CREATE TABLE "analytics"."t1" WITH (external_location = '
            f"'{ctas_location}', format = 'PARQUET') AS SELECT 1 AS a"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
        output_location=output_location,
    )
    for key in ("t1/part-00001-b.parquet", "t1/part-00000-a.parquet"):
        stack.s3.put_object(
            Bucket=stack.ctas_bucket, Key=key, Body=b"parquet-bytes"
        )

    asyncio.run(stack.writer.write(record, PLACEHOLDER_PAGE))

    query_id = record.query_execution_id
    manifest_key = f"analytics/{query_id}-manifest.csv"
    manifest_path = f"s3://{stack.results_bucket}/{manifest_key}"
    assert record.data_manifest_location == manifest_path
    body = stack.object_bytes(stack.results_bucket, manifest_key)
    # Wrangler splits on "\n" and drops empties (_read.py:62-81).
    paths = [line for line in body.decode("utf-8").split("\n") if line]
    assert paths == [
        f"{ctas_location}part-00000-a.parquet",
        f"{ctas_location}part-00001-b.parquet",
    ]
    assert stack.object_bytes(
        stack.results_bucket, f"analytics/{query_id}.metadata"
    )
