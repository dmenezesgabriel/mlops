"""PC-6 live smoke: the composed production executor round-trips end to end.

Builds the query plane through ``main.build_query_executor`` — the exact
composition the app root wires at import — and drives one query through the
running stack with real boto3 → uvicorn → Trino → moto-S3: StartQueryExecution
returns an id, the execution reaches SUCCEEDED with artifacts on S3, and
GetQueryResults serves the inline row. Contrasts with the AR/QE suites, which
rebind bespoke writers; here the full product composition (writer +
snapshotter) runs. Skips when the compose Trino service is unreachable.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import boto3
import httpx
import pytest
from athena_local.main import (
    build_query_executor,
    execution_store,
    reset_query_plane,
    workgroup_store,
)
from athena_local.query_executions import register_query_execution_handlers
from botocore.client import BaseClient
from moto.backends import get_backend
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8080")


@dataclass
class ComposedPlaneHarness:
    """The live stack plus a throwaway result bucket for the smoke query."""

    athena: BaseClient
    s3: BaseClient
    prefix: str
    bucket: str


@pytest.fixture()
def composed_plane_harness(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
) -> Iterator[ComposedPlaneHarness]:
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
    bucket = f"athena-pc6-results-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=bucket)
    prefix = f"s3://{bucket}/results/"

    executor = build_query_executor(
        execution_store, TRINO_URL, live_moto_server.url
    )
    register_query_execution_handlers(
        execution_store, executor, workgroup_store
    )
    try:
        yield ComposedPlaneHarness(
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
        reset_query_plane()


def test_composed_executor_runs_query_end_to_end(
    composed_plane_harness: ComposedPlaneHarness,
) -> None:
    harness = composed_plane_harness
    started = harness.athena.start_query_execution(
        QueryString="SELECT 1 AS one",
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]

    execution = _poll_until_terminal(harness.athena, query_id)

    assert execution["Status"]["State"] == "SUCCEEDED"
    assert execution["ResultConfiguration"]["OutputLocation"] == (
        f"{harness.prefix}{query_id}.csv"
    )
    contents = harness.s3.list_objects_v2(
        Bucket=harness.bucket, Prefix="results/"
    )["Contents"]
    assert sorted(item["Key"] for item in contents) == [
        f"results/{query_id}.csv",
        f"results/{query_id}.csv.metadata",
    ]

    inline = harness.athena.get_query_results(
        QueryExecutionId=query_id, MaxResults=5
    )["ResultSet"]
    assert inline["Rows"][0]["Data"] == [{"VarCharValue": "one"}]
    assert inline["Rows"][1]["Data"] == [{"VarCharValue": "1"}]


def _poll_until_terminal(
    client: BaseClient, execution_id: str, deadline_seconds: float = 30.0
) -> dict[str, Any]:
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
