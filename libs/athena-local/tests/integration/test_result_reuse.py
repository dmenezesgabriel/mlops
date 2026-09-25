"""Integration: ResultReuseConfiguration re-answers a recent identical run.

Real boto3 → uvicorn → Trino → moto-S3 round trip exercising AWS's
documented reuse contract (UG "Reusing query results"): a second identical
submission with ``ResultReuseByAgeConfiguration.Enabled`` bypasses the
engine, reports ``Statistics.ResultReuseInformation.ReusedPreviousResult``
and the source execution's OutputLocation, and writes no new artifact.
Skips when the compose Trino service is unreachable.
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
from athena_local.executions import ExecutionStore
from athena_local.executor import QueryExecutor
from athena_local.main import reset_query_plane
from athena_local.query_executions import register_query_execution_handlers
from athena_local.s3_writer import S3Writer
from athena_local.state import WorkGroupStore
from athena_local.trino_client import create_trino_client
from botocore.client import BaseClient
from moto.backends import get_backend
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8080")

REUSE_ENABLED = {
    "ResultReuseByAgeConfiguration": {"Enabled": True, "MaxAgeInMinutes": 60}
}


@dataclass
class ReuseHarness:
    """The live stack plus the result prefix the queries report back."""

    athena: BaseClient
    s3: BaseClient
    prefix: str
    bucket: str


@pytest.fixture()
def reuse_harness(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
) -> Iterator[ReuseHarness]:
    try:
        httpx.get(f"{TRINO_URL}/v1/info", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(
            f"Trino unreachable at {TRINO_URL}; compose services are down"
        )
    # moto backends are process-global; the unique bucket keeps this fixture
    # isolated from sibling suites' resets.
    get_backend("s3").reset()
    s3 = boto3.client(
        "s3",
        endpoint_url=live_moto_server.url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    bucket = f"athena-reuse-results-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=bucket)

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
        yield ReuseHarness(
            athena=boto3.client(
                "athena",
                endpoint_url=live_athena_server.endpoint_url,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            ),
            s3=s3,
            prefix=f"s3://{bucket}/results/",
            bucket=bucket,
        )
    finally:
        reset_query_plane()


def test_identical_enabled_run_reuses_the_previous_result(
    reuse_harness: ReuseHarness,
) -> None:
    harness = reuse_harness
    first = _run_to_terminal(harness, "SELECT 42 AS answer", REUSE_ENABLED)

    second = _run_to_terminal(harness, "SELECT 42 AS answer", REUSE_ENABLED)

    assert second["Status"]["State"] == "SUCCEEDED"
    # The reuse markers the consumers read: the echoed configuration and the
    # reused flag (service-2.json QueryExecution members).
    assert (
        second["ResultReuseConfiguration"]["ResultReuseByAgeConfiguration"][
            "Enabled"
        ]
        is True
    )
    assert second["Statistics"]["ResultReuseInformation"] == {
        "ReusedPreviousResult": True
    }
    assert (
        second["ResultConfiguration"]["OutputLocation"]
        == (first["ResultConfiguration"]["OutputLocation"])
    )
    assert (
        second["Statistics"]["ResultReuseInformation"]
        != (first["Statistics"]["ResultReuseInformation"])
    )
    assert first["Statistics"]["ResultReuseInformation"] == {
        "ReusedPreviousResult": False
    }

    # No second artifact landed: only the first execution's files exist.
    contents = harness.s3.list_objects_v2(
        Bucket=harness.bucket, Prefix="results/"
    )["Contents"]
    first_id = first["QueryExecutionId"]
    assert sorted(item["Key"] for item in contents) == [
        f"results/{first_id}.csv",
        f"results/{first_id}.csv.metadata",
    ]
    # Inline results answer the same rows the first run produced.
    assert _result_rows(harness, first_id) == _result_rows(
        harness, second["QueryExecutionId"]
    )


def test_disabled_reuse_runs_fresh_and_writes_its_own_artifact(
    reuse_harness: ReuseHarness,
) -> None:
    harness = reuse_harness
    enabled = _run_to_terminal(harness, "SELECT 1", REUSE_ENABLED)

    disabled = _run_to_terminal(
        harness,
        "SELECT 1",
        {"ResultReuseByAgeConfiguration": {"Enabled": False}},
    )

    assert disabled["Status"]["State"] == "SUCCEEDED"
    assert disabled["Statistics"]["ResultReuseInformation"] == {
        "ReusedPreviousResult": False
    }
    assert (
        disabled["ResultConfiguration"]["OutputLocation"]
        != (enabled["ResultConfiguration"]["OutputLocation"])
    )


def _run_to_terminal(
    harness: ReuseHarness,
    query: str,
    reuse_configuration: dict[str, object],
    deadline_seconds: float = 30.0,
) -> dict[str, object]:
    query_id = harness.athena.start_query_execution(
        QueryString=query,
        ResultConfiguration={"OutputLocation": harness.prefix},
        ResultReuseConfiguration=reuse_configuration,
    )["QueryExecutionId"]
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        execution = harness.athena.get_query_execution(
            QueryExecutionId=query_id
        )["QueryExecution"]
        if execution["Status"]["State"] in {
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
        }:
            return execution
        time.sleep(0.2)
    pytest.fail(
        f"execution {query_id} did not reach a terminal state within "
        f"{deadline_seconds:.0f}s"
    )


def _result_rows(
    harness: ReuseHarness, query_id: str
) -> list[list[dict[str, object]]]:
    result_set = harness.athena.get_query_results(QueryExecutionId=query_id)[
        "ResultSet"
    ]
    return [row["Data"] for row in result_set["Rows"]]
