"""AR-2 integration: GetQueryExecution reports the full artifact path.

Real boto3 → uvicorn → Trino round trip where the artifact writer is the real
``ArtifactWriter`` over a live moto S3, so the ``OutputLocation`` the wire
reports names the exact object the query produced (ADR-0007 #2): a DML SELECT
answers ``{prefix}{QueryID}.csv`` and a UTILITY statement ``{prefix}{QueryID}.txt``
— the suffixes wrangler keys its file reads on
(awswrangler/athena/_read.py:220, _utils.py:196). Skips when the compose Trino
service is unreachable.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import boto3
import httpx
import pytest
from athena_local.artifacts import ArtifactWriter
from athena_local.dispatch import OPERATION_HANDLERS
from athena_local.executions import ExecutionStore
from athena_local.executor import QueryExecutor
from athena_local.query_executions import register_query_execution_handlers
from athena_local.s3_writer import S3Writer
from athena_local.state import WorkGroupStore
from athena_local.trino_client import create_trino_client
from botocore.client import BaseClient
from moto.backends import get_backend
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8080")
QUERY_PLANE_OPERATIONS = {
    "StartQueryExecution",
    "StopQueryExecution",
    "GetQueryExecution",
    "BatchGetQueryExecution",
    "GetQueryResults",
    "GetQueryRuntimeStatistics",
}


@dataclass
class OutputLocationHarness:
    """The live stack plus the result prefix the queries report back."""

    athena: BaseClient
    s3: BaseClient
    prefix: str
    bucket: str


@pytest.fixture()
def output_location_harness(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
) -> Iterator[OutputLocationHarness]:
    try:
        httpx.get(f"{TRINO_URL}/v1/info", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(
            f"Trino unreachable at {TRINO_URL}; compose services are down"
        )
    # moto backends are process-global; the unique bucket keeps this fixture
    # isolated from the writer suite's resets.
    get_backend("s3").reset()
    s3 = boto3.client(
        "s3",
        endpoint_url=live_moto_server.url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    bucket = f"athena-ar2-results-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=bucket)
    prefix = f"s3://{bucket}/results/"

    store = ExecutionStore()
    register_query_execution_handlers(
        store,
        QueryExecutor(
            store=store,
            client=create_trino_client(TRINO_URL),
            writer=ArtifactWriter(S3Writer.for_endpoint(live_moto_server.url)),
        ),
        WorkGroupStore(),
    )
    try:
        yield OutputLocationHarness(
            athena=boto3.client(
                "athena",
                endpoint_url=live_athena_server.endpoint_url,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            ),
            s3=s3,
            prefix=prefix,
            bucket=bucket,
        )
    finally:
        for operation in QUERY_PLANE_OPERATIONS:
            OPERATION_HANDLERS.pop(operation, None)


def test_select_reports_full_csv_output_location(
    output_location_harness: OutputLocationHarness,
) -> None:
    harness = output_location_harness
    started = harness.athena.start_query_execution(
        QueryString="SELECT 1",
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]
    execution = _poll_until_terminal(harness.athena, query_id)

    assert execution["Status"]["State"] == "SUCCEEDED"
    assert execution["ResultConfiguration"]["OutputLocation"] == (
        f"{harness.prefix}{query_id}.csv"
    )
    # The reported path is a real object, written before SUCCEEDED (ADR-0009
    # #4), with the header-quoted CSV byte shape (ADR-0010).
    contents = harness.s3.list_objects_v2(
        Bucket=harness.bucket, Prefix="results/"
    )["Contents"]
    assert sorted(item["Key"] for item in contents) == [
        f"results/{query_id}.csv",
        f"results/{query_id}.csv.metadata",
    ]


def test_utility_reports_full_txt_output_location(
    output_location_harness: OutputLocationHarness,
) -> None:
    harness = output_location_harness
    started = harness.athena.start_query_execution(
        QueryString="SHOW FUNCTIONS",
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]
    execution = _poll_until_terminal(harness.athena, query_id)

    assert execution["Status"]["State"] == "SUCCEEDED"
    assert execution["ResultConfiguration"]["OutputLocation"] == (
        f"{harness.prefix}{query_id}.txt"
    )
    contents = harness.s3.list_objects_v2(
        Bucket=harness.bucket, Prefix="results/"
    )["Contents"]
    assert sorted(item["Key"] for item in contents) == [
        f"results/{query_id}.txt",
        f"results/{query_id}.txt.metadata",
    ]


def _poll_until_terminal(
    client: BaseClient, execution_id: str, deadline_seconds: float = 30.0
) -> dict[str, object]:
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        execution = client.get_query_execution(QueryExecutionId=execution_id)[
            "QueryExecution"
        ]
        if execution["Status"]["State"] in {
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
        }:
            return execution
        time.sleep(0.2)
    pytest.fail(
        f"execution {execution_id} did not reach a terminal state within "
        f"{deadline_seconds:.0f}s"
    )
