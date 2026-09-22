"""QE-7 integration: boto3 → uvicorn → Trino → moto S3 EXECUTE round trip.

A prepared statement is created through the live app's control plane, then
``start_query_execution`` runs ``EXECUTE "st" USING 'Washington'`` against the
real compose Trino with the real ``ArtifactWriter`` on moto S3. The query
plane is re-registered with a bespoke executor/store wired to Trino and moto
— the pattern from test_output_location.py — while the prepared statement
store stays the app's own (imported from ``athena_local.main``), so the
statement created over the wire is exactly the one the resolver reads.
Missing statements and parameter-count mismatches are FAILED executions
(never 400s), with the submitted EXECUTE text kept as the wire ``Query``.
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
from athena_local.main import prepared_statement_store, reset_query_plane
from athena_local.query_executions import register_query_execution_handlers
from athena_local.s3_writer import S3Writer
from athena_local.state import WorkGroupStore
from athena_local.trino_client import create_trino_client
from botocore.client import BaseClient
from moto.backends import get_backend
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8080")


@dataclass
class PreparedExecutionHarness:
    """The live stack plus the result prefix the EXECUTE queries report back."""

    athena: BaseClient
    s3: BaseClient
    prefix: str
    bucket: str


@pytest.fixture()
def prepared_execution_harness(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
) -> Iterator[PreparedExecutionHarness]:
    try:
        httpx.get(f"{TRINO_URL}/v1/info", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(
            f"Trino unreachable at {TRINO_URL}; compose services are down"
        )
    # moto backends are process-global; the unique bucket keeps this fixture
    # isolated from the other suites' resets.
    get_backend("s3").reset()
    s3 = boto3.client(
        "s3",
        endpoint_url=live_moto_server.url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    bucket = f"athena-qe7-results-{uuid.uuid4().hex}"
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
        # The live app's control plane writes statements into this same
        # store, so statements created over boto3 resolve on EXECUTE.
        prepared_statement_store,
    )
    try:
        yield PreparedExecutionHarness(
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


def test_execute_with_inline_using_round_trip(
    prepared_execution_harness: PreparedExecutionHarness,
) -> None:
    harness = prepared_execution_harness
    harness.athena.create_prepared_statement(
        StatementName="flights_stmt",
        WorkGroup="primary",
        QueryStatement=(
            "SELECT * FROM (VALUES ('Washington'), ('Seattle')) AS t(origin) "
            "WHERE origin = ?"
        ),
    )

    query = "EXECUTE \"flights_stmt\" USING 'Washington'"
    started = harness.athena.start_query_execution(
        QueryString=query,
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]
    execution = _poll_until_terminal(harness.athena, query_id)

    # The wire Query stays the submitted EXECUTE text while the resolved
    # statement's DML/SELECT classification drives the .csv artifacts.
    assert execution["Status"]["State"] == "SUCCEEDED"
    assert execution["Query"] == query
    assert execution["StatementType"] == "DML"
    assert execution["SubstatementType"] == "SELECT"
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
    rows = harness.athena.get_query_results(QueryExecutionId=query_id)[
        "ResultSet"
    ]["Rows"]
    assert rows[1]["Data"] == [{"VarCharValue": "Washington"}]


def test_execute_with_execution_parameters_round_trip(
    prepared_execution_harness: PreparedExecutionHarness,
) -> None:
    harness = prepared_execution_harness
    harness.athena.create_prepared_statement(
        StatementName="number_stmt",
        WorkGroup="primary",
        QueryStatement=("SELECT * FROM (VALUES (1), (2)) AS t(n) WHERE n = ?"),
    )

    started = harness.athena.start_query_execution(
        QueryString='EXECUTE "number_stmt"',
        ExecutionParameters=["2"],
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]
    execution = _poll_until_terminal(harness.athena, query_id)

    assert execution["Status"]["State"] == "SUCCEEDED"
    rows = harness.athena.get_query_results(QueryExecutionId=query_id)[
        "ResultSet"
    ]["Rows"]
    assert rows[1]["Data"] == [{"VarCharValue": "2"}]


def test_execute_missing_statement_is_failed_execution(
    prepared_execution_harness: PreparedExecutionHarness,
) -> None:
    harness = prepared_execution_harness
    query = "EXECUTE no_such_stmt"
    started = harness.athena.start_query_execution(
        QueryString=query,
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]
    execution = _poll_until_terminal(harness.athena, query_id)

    assert execution["Status"]["State"] == "FAILED"
    assert execution["Status"]["StateChangeReason"] == (
        "PreparedStatement no_such_stmt was not found in workGroup primary"
    )
    assert execution["Query"] == query
    assert execution["StatementType"] == "UTILITY"


def test_execute_count_mismatch_is_failed_execution(
    prepared_execution_harness: PreparedExecutionHarness,
) -> None:
    harness = prepared_execution_harness
    harness.athena.create_prepared_statement(
        StatementName="two_slots",
        WorkGroup="primary",
        QueryStatement=(
            "SELECT * FROM (VALUES (1), (2)) AS t(n) WHERE n = ? AND n > ?"
        ),
    )

    started = harness.athena.start_query_execution(
        QueryString='EXECUTE "two_slots"',
        ExecutionParameters=["1"],
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    query_id = started["QueryExecutionId"]
    execution = _poll_until_terminal(harness.athena, query_id)

    assert execution["Status"]["State"] == "FAILED"
    assert execution["Status"]["StateChangeReason"] == (
        "Incorrect number of parameters: expected 2 but found 1"
    )


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
