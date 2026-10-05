"""Managed-results integration: workgroups over the live stack.

A real boto3 → uvicorn → Trino round trip on a workgroup whose
ManagedQueryResultsConfiguration.Enabled is true: StartQueryExecution carries
no ResultConfiguration (the model forbids an OutputLocation on a managed
workgroup, and awswrangler omits it — awswrangler/athena/_utils.py:105-109),
the execution must SUCCEEDED without any S3 artifact, GetQueryExecution must
report a ResultConfiguration without OutputLocation, and the rows must be
servable inline via GetQueryResults — the exact read path wrangler's managed
flow takes (awswrangler/athena/_read.py:450). Skips when the compose Trino
service is unreachable.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import boto3
import httpx
import pytest
from athena_local.artifacts import ArtifactWriter
from athena_local.common_schemas import ManagedQueryResultsConfiguration
from athena_local.executions import ExecutionStore
from athena_local.executor import QueryExecutor
from athena_local.main import reset_query_plane
from athena_local.query_executions import register_query_execution_handlers
from athena_local.s3_writer import S3Writer
from athena_local.state import WorkGroupStore
from athena_local.trino_client import create_trino_client
from athena_local.workgroup_schemas import WorkGroupConfiguration
from botocore.client import BaseClient
from moto.backends import get_backend
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8485")

MANAGED_WORKGROUP_NAME = "managed-results"


@dataclass
class ManagedResultsHarness:
    """The live stack with a pre-created managed-results workgroup."""

    athena: BaseClient


@pytest.fixture()
def managed_results_harness(
    live_athena_server: LiveAthenaServer,
    live_moto_server: LiveMotoServer,
) -> Iterator[ManagedResultsHarness]:
    try:
        httpx.get(f"{TRINO_URL}/v1/info", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(
            f"Trino unreachable at {TRINO_URL}; compose services are down"
        )
    # moto backends are process-global; reset keeps suites isolated even
    # though a managed execution should never write S3 objects.
    get_backend("s3").reset()

    workgroups = WorkGroupStore()
    workgroups.create(
        MANAGED_WORKGROUP_NAME,
        WorkGroupConfiguration(
            managed_query_results_configuration=(
                ManagedQueryResultsConfiguration(enabled=True)
            )
        ),
        None,
        [],
    )

    store = ExecutionStore()
    register_query_execution_handlers(
        store,
        QueryExecutor(
            store=store,
            client=create_trino_client(TRINO_URL),
            writer=ArtifactWriter(S3Writer.for_endpoint(live_moto_server.url)),
        ),
        workgroups,
    )
    try:
        yield ManagedResultsHarness(
            athena=boto3.client(
                "athena",
                endpoint_url=live_athena_server.endpoint_url,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            ),
        )
    finally:
        reset_query_plane()


def test_managed_workgroup_query_succeeds_without_output_location(
    managed_results_harness: ManagedResultsHarness,
) -> None:
    athena = managed_results_harness.athena
    started = athena.start_query_execution(
        QueryString="SELECT x FROM (VALUES 1, 2) AS t(x) ORDER BY x",
        WorkGroup=MANAGED_WORKGROUP_NAME,
    )
    query_id = started["QueryExecutionId"]

    execution = _poll_until_terminal(athena, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED"
    # The managed path reports a ResultConfiguration member with no
    # OutputLocation — the shape wrangler's managed read asserts on
    # (awswrangler/tests/unit/test_athena.py:125).
    result_configuration: dict[str, Any] = execution["ResultConfiguration"]
    assert "OutputLocation" not in result_configuration

    rows = athena.get_query_results(QueryExecutionId=query_id)["ResultSet"][
        "Rows"
    ]
    assert [_page_values(row) for row in rows] == [
        ["x"],
        ["1"],
        ["2"],
    ]


def test_managed_workgroup_ignores_request_output_location(
    managed_results_harness: ManagedResultsHarness,
) -> None:
    athena = managed_results_harness.athena
    started = athena.start_query_execution(
        QueryString="SELECT 42 AS answer",
        WorkGroup=MANAGED_WORKGROUP_NAME,
        ResultConfiguration={"OutputLocation": "s3://must-be-ignored/"},
    )
    query_id = started["QueryExecutionId"]

    execution = _poll_until_terminal(athena, query_id)
    assert execution["Status"]["State"] == "SUCCEEDED"
    assert "OutputLocation" not in execution["ResultConfiguration"]


def test_awswrangler_get_workgroup_config_reads_managed_workgroup(
    managed_results_harness: ManagedResultsHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import awswrangler as wr

    monkeypatch.setattr(
        wr.config,
        "athena_endpoint_url",
        managed_results_harness.athena.meta.endpoint_url,
    )

    # GetWorkGroup serves the app's module-level store, so the managed
    # workgroup is created through the same API wrangler would use.
    managed_results_harness.athena.create_work_group(
        Name=MANAGED_WORKGROUP_NAME,
        Configuration={
            "ManagedQueryResultsConfiguration": {"Enabled": True},
        },
    )

    config = wr.athena._utils._get_workgroup_config(
        session=_wrangler_session(), workgroup=MANAGED_WORKGROUP_NAME
    )

    assert config.managed_results is True
    assert config.s3_output is None
    # EnforceWorkGroupConfiguration defaults to True on create (moto parity:
    # workgroup_schemas.defaulted, moto/athena WorkGroup.__init__) — the
    # same shape wrangler's own `workgroup_managed` fixture uses.
    assert config.enforced is True


def _wrangler_session() -> boto3.Session:
    return boto3.Session(
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


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
