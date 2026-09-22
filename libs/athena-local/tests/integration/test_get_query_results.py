"""AR-3 integration: GetQueryResults pagination over the real botocore paginator.

A live boto3 → uvicorn → Trino → moto-S3 round trip: StartQueryExecution runs
a bounded VALUES SELECT, then the results are walked with botocore's actual
``get_query_results`` paginator — the exact path awswrangler's
``_fetch_api_result`` takes (awswrangler/athena/_read.py:335-384) — with a
small MaxResults. The merged pages must equal the full result set with the
header stripped exactly once and no loss or duplication, proving the
MaxResults/NextToken semantics match what the paginator expects. Skips when
the compose Trino service is unreachable.
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
class InlineResultsHarness:
    """The live stack plus a throwaway result bucket for started queries."""

    athena: BaseClient
    prefix: str


@pytest.fixture()
def inline_results_harness(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
) -> Iterator[InlineResultsHarness]:
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
    bucket = f"athena-ar3-results-{uuid.uuid4().hex}"
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
        yield InlineResultsHarness(
            athena=boto3.client(
                "athena",
                endpoint_url=live_athena_server.endpoint_url,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            ),
            prefix=f"s3://{bucket}/results/",
        )
    finally:
        for operation in QUERY_PLANE_OPERATIONS:
            OPERATION_HANDLERS.pop(operation, None)


def test_botocore_paginator_walks_pages_losslessly(
    inline_results_harness: InlineResultsHarness,
) -> None:
    harness = inline_results_harness
    query_id = _start_values_query(harness)
    _poll_until_terminal(harness.athena, query_id)

    paginator = harness.athena.get_paginator("get_query_results")
    pages = list(
        paginator.paginate(
            QueryExecutionId=query_id,
            PaginationConfig={"PageSize": 2},
        )
    )

    # 6 data rows at MaxResults 2 split into header+2, 2, 2 — the paginator
    # followed each NextToken and stopped when the last page carried none.
    assert len(pages) == 3
    merged_rows: list[list[str]] = []
    first_page = True
    for page in pages:
        rows = page["ResultSet"]["Rows"]
        if first_page:
            assert _page_values(rows[0]) == ["x"], "header must be page zero"
            rows = rows[1:]
            first_page = False
        merged_rows.extend(_page_values(row) for row in rows)

    assert merged_rows == [[str(number)] for number in range(1, 7)]
    assert (
        pages[0]["ResultSet"]["ResultSetMetadata"]["ColumnInfo"][0]["Name"]
        == "x"
    )


def test_max_results_and_next_token_round_trip(
    inline_results_harness: InlineResultsHarness,
) -> None:
    harness = inline_results_harness
    query_id = _start_values_query(harness)
    _poll_until_terminal(harness.athena, query_id)

    first = harness.athena.get_query_results(
        QueryExecutionId=query_id, MaxResults=4
    )
    rows = first["ResultSet"]["Rows"]
    assert [_page_values(row) for row in rows[1:]] == [
        ["1"],
        ["2"],
        ["3"],
        ["4"],
    ]
    assert first["NextToken"] == "4"

    second = harness.athena.get_query_results(
        QueryExecutionId=query_id, MaxResults=2, NextToken=first["NextToken"]
    )
    assert [_page_values(row) for row in second["ResultSet"]["Rows"]] == [
        ["5"],
        ["6"],
    ]
    assert "NextToken" not in second


def _start_values_query(harness: InlineResultsHarness) -> str:
    started = harness.athena.start_query_execution(
        QueryString="SELECT x FROM (VALUES 1, 2, 3, 4, 5, 6) AS t(x)",
        ResultConfiguration={"OutputLocation": harness.prefix},
    )
    return started["QueryExecutionId"]


def _page_values(row: dict[str, Any]) -> list[str]:
    """Strip a wire Row down to its VarCharValue cell strings."""
    return [
        cell["VarCharValue"]
        for cell in row["Data"]
        if isinstance(cell, dict) and "VarCharValue" in cell
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
