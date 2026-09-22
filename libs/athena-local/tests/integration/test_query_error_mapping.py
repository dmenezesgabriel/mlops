"""QE-5 integration: Trino's error text becomes Athena's wire shapes.

The six query-plane operations are composed by the production root in
``main`` (PC-6); this fixture rebinds them to a real ``TrinoClient`` and a
no-op writer so boto3 round-trips the JSON-1.1 surface end to end over real
HTTP without touching S3:
StartQueryExecution rejects bad syntax with the shaped 400 before any
execution exists, and an analysis error FAILs the execution with Trino's
StateChangeReason verbatim — the two surfaces awswrangler maps to
InvalidCtasApproachQuery / QueryFailed
(research_repos/aws-sdk-pandas/awswrangler/athena/_utils.py:888-898,
_read.py:820-832). Skips when the compose Trino service is unreachable.

The duplicate-column CTAS never creates a table (Trino rejects it during
analysis), but each run still drops its target best-effort so a buggy
emulator can never leave junk in the shared analytics schema.
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator

import boto3
import httpx
import pytest
from athena_local.executions import ExecutionStore, QueryExecutionRecord
from athena_local.executor import QueryExecutor
from athena_local.main import reset_query_plane
from athena_local.query_executions import register_query_execution_handlers
from athena_local.state import WorkGroupStore
from athena_local.trino_client import TrinoPage, create_trino_client
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from tests.integration.conftest import LiveAthenaServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8080")
RESULT_LOCATION = "s3://athena-local/results/"
CTAS_TABLE_PREFIX = "athena_local_qe5_dup"


class NoOpResultWriter:
    """Artifact writer that never runs: QE-5 only exercises failed executions."""

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        return None


@pytest.fixture()
def query_plane_client(
    live_athena_server: LiveAthenaServer,
) -> Iterator[BaseClient]:
    try:
        httpx.get(f"{TRINO_URL}/v1/info", timeout=2.0).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(
            f"Trino unreachable at {TRINO_URL}; compose services are down"
        )

    store = ExecutionStore()
    register_query_execution_handlers(
        store,
        QueryExecutor(
            store=store,
            client=create_trino_client(TRINO_URL),
            writer=NoOpResultWriter(),
        ),
        WorkGroupStore(),
    )
    try:
        yield boto3.client(
            "athena",
            endpoint_url=live_athena_server.endpoint_url,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
    finally:
        reset_query_plane()


def test_bad_syntax_rejects_start_with_shaped_400(
    query_plane_client: BaseClient,
) -> None:
    with pytest.raises(ClientError) as exc_info:
        query_plane_client.start_query_execution(
            QueryString="SELEC 1",
            ResultConfiguration={"OutputLocation": RESULT_LOCATION},
        )

    response = exc_info.value.response
    assert response["Error"]["Code"] == "InvalidRequestException"
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 400
    # wrangler sniffs this prefix (and "extraneous input" inside the Trino
    # text) at awswrangler/athena/_utils.py:888-898.
    assert response["Error"]["Message"].startswith("Exception parsing query")
    assert "mismatched input 'SELEC'" in response["Error"]["Message"]


def test_duplicate_column_ctas_fails_with_trino_reason_verbatim(
    query_plane_client: BaseClient,
) -> None:
    table = f"{CTAS_TABLE_PREFIX}_{uuid.uuid4().hex[:8]}"
    try:
        started = query_plane_client.start_query_execution(
            QueryString=(
                "CREATE TABLE "
                f"{table} WITH (external_location = 's3://qe5/bucket/') "
                "AS SELECT 1 AS a, 2 AS a"
            ),
            QueryExecutionContext={"Database": "analytics"},
            ResultConfiguration={"OutputLocation": RESULT_LOCATION},
        )

        execution = _poll_until_terminal(
            query_plane_client, started["QueryExecutionId"]
        )

        assert execution["Status"]["State"] == "FAILED"
        assert "specified more than once" in (
            execution["Status"]["StateChangeReason"] or ""
        )
    finally:
        _drop_table_best_effort(table)


def _poll_until_terminal(
    client: BaseClient, execution_id: str, deadline_seconds: float = 20.0
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


def _drop_table_best_effort(table: str) -> None:
    """DROP TABLE IF EXISTS straight against Trino, ignoring transport noise."""
    try:
        response = httpx.post(
            f"{TRINO_URL}/v1/statement",
            content=f"DROP TABLE IF EXISTS hive.analytics.{table}".encode(),
            headers={
                "X-Trino-User": "athena-local-test",
                "Content-Type": "text/plain",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        next_uri = response.json().get("nextUri")
        while next_uri is not None:
            page = httpx.get(next_uri, timeout=30.0)
            page.raise_for_status()
            next_uri = page.json().get("nextUri")
    except httpx.HTTPError:
        pass  # best-effort clean-up; a leftover table fails the run loudly
