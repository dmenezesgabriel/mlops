"""CS-2b1: awswrangler read-path consumer suite against the live data plane.

Drives real awswrangler 3.17.1 through the emulator (in-process uvicorn,
random port) and the **compose moto container** as the shared data plane: the
emulator's artifact writer points at moto via its bridge IP
(``ATHENA_LOCAL_MOTO_ENDPOINT_URL``), Trino writes query results to the same
moto internally (``moto:5000``), and wrangler reads the artifacts back through
an S3 client on that same moto — so the CSV/cache/inline views observe one
object store (this is why the in-process ``LiveMotoServer`` is deliberately
NOT used here; FR-06-style round-trips would disagree on object identity).

Skip semantics mirror ``test_composition_root``: the suite skips when the
compose Trino coordinator or the bridge moto is unreachable, so a cold stack
never fails CI (the M5 compose stack is what CS-2b2/CS-3 will pin instead).

Wrangler endpoint wiring is the FR-19 mechanism itself: per-service
``AWS_ENDPOINT_URL_ATHENA`` / ``AWS_ENDPOINT_URL_S3`` / ``AWS_ENDPOINT_URL_GLUE``
env vars on a boto3 session, so every client wrangler creates (athena, s3, glue)
lands on the right host without explicit endpoint kwargs.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import awswrangler as wr
import boto3
import botocore.exceptions
import httpx
import pandas as pd
import pytest
from athena_local.main import (
    build_query_executor,
    execution_store,
    prepared_statement_store,
    register_query_execution_handlers,
    reset_query_plane,
    workgroup_store,
)
from botocore.client import BaseClient
from botocore.config import Config
from tests.integration.conftest import LiveAthenaServer

TRINO_URL = os.environ.get("ATHENA_LOCAL_TRINO_URL", "http://localhost:8080")
BRIDGE_URL_ENV = "ATHENA_LOCAL_MOTO_ENDPOINT_URL"
# The compose moto service publishes no host port; reach it on the mlops_net
# bridge. Override the env var when docker re-creates the network with a
# different subnet.
BRIDGE_URL_DEFAULT = "http://172.19.0.2:5000"

MIXED_SQL = """
SELECT
  CAST(1 AS INTEGER)           AS one,
  CAST(1.5 AS DOUBLE)          AS ratio,
  CAST(12.34 AS DECIMAL(6, 2)) AS amount,
  TRUE                         AS flag,
  DATE '2023-06-15'            AS day,
  TIMESTAMP '2023-06-15 10:20:30.123' AS ts,
  CAST(NULL AS VARCHAR)        AS nothing
"""

CACHE_SETTINGS = {"max_cache_seconds": 90}


@dataclass
class ConsumerHarness:
    """Live stack endpoints: throwaway bucket + database on the shared moto."""

    athena: BaseClient
    s3: BaseClient
    glue: BaseClient
    bucket: str
    prefix: str
    database: str


def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        httpx.get(url, timeout=timeout).raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def _bridge_url() -> str:
    """Resolve the bridge moto URL from the environment, defaulting to the
    observed compose subnet."""
    url = os.environ.get(BRIDGE_URL_ENV, BRIDGE_URL_DEFAULT)
    probe = boto3.client(
        "s3",
        endpoint_url=url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            connect_timeout=2, read_timeout=5, retries={"max_attempts": 1}
        ),
    )
    try:
        probe.list_buckets()
    except botocore.exceptions.BotoCoreError:
        pytest.skip(f"compose moto unreachable at {url}; set {BRIDGE_URL_ENV}")
    return url


@pytest.fixture()
def consumer_harness(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> ConsumerHarness:
    """Bind wrangler's boto3 session and the emulator to the live stack."""
    if not _probe(f"{TRINO_URL}/v1/info"):
        pytest.skip(
            f"Trino unreachable at {TRINO_URL}; compose services are down"
        )
    bridge = _bridge_url()

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv(
        "AWS_ENDPOINT_URL_ATHENA", live_athena_server.endpoint_url
    )
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", bridge)
    monkeypatch.setenv("AWS_ENDPOINT_URL_GLUE", bridge)

    suffix = uuid.uuid4().hex
    bucket = f"athena-cs2b1-{suffix}"
    database = f"cs2b1_{suffix}"
    s3 = boto3.client(
        "s3",
        endpoint_url=bridge,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    glue = boto3.client(
        "glue",
        endpoint_url=bridge,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    s3.create_bucket(Bucket=bucket)
    glue.create_database(DatabaseInput={"Name": database})

    executor = build_query_executor(execution_store, TRINO_URL, bridge)
    register_query_execution_handlers(
        execution_store, executor, workgroup_store, prepared_statement_store
    )
    try:
        yield ConsumerHarness(
            athena=boto3.client(
                "athena",
                endpoint_url=live_athena_server.endpoint_url,
                region_name="us-east-1",
                aws_access_key_id="test",
                aws_secret_access_key="test",
            ),
            s3=s3,
            glue=glue,
            bucket=bucket,
            prefix=f"s3://{bucket}/results/",
            database=database,
        )
    finally:
        reset_query_plane()
        try:
            _delete_objects_and_bucket(s3, bucket)
        except (
            botocore.exceptions.BotoCoreError,
            botocore.exceptions.ClientError,
        ):
            pass
        try:
            glue.delete_database(Name=database)
        except (
            botocore.exceptions.BotoCoreError,
            botocore.exceptions.ClientError,
        ):
            pass


def _delete_objects_and_bucket(s3: BaseClient, bucket: str) -> None:
    """Drop every object then the throwaway bucket (teardown, best effort).

    An empty ``Delete.Objects`` list is rejected by moto's XML schema
    (MalformedXML), so the object pass only runs when keys exist.
    """
    contents = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
    if contents:
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": item["Key"]} for item in contents]},
        )
    s3.delete_bucket(Bucket=bucket)


def _mixed_frame() -> pd.DataFrame:
    """The semantic rows MIXED_SQL must round-trip to, path-agnostic."""
    return pd.DataFrame(
        {
            "one": [1],
            "ratio": [1.5],
            "amount": [Decimal("12.34")],
            "flag": [True],
            "day": [date(2023, 6, 15)],
            "ts": [datetime(2023, 6, 15, 10, 20, 30, 123000)],
            "nothing": [pd.NA],
        }
    )


def _assert_mixed_rows(frame: pd.DataFrame) -> None:
    """Value equality for the mixed-type query, dtype-agnostic."""
    pd.testing.assert_frame_equal(
        frame.reset_index(drop=True), _mixed_frame(), check_dtype=False
    )


def test_read_sql_query_csv_path_round_trips_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """FR-04: default non-managed ``primary`` reads the csv artifact back."""
    primary = consumer_harness.athena.get_work_group(WorkGroup="primary")[
        "WorkGroup"
    ]["Configuration"]
    assert "ManagedQueryResultsConfiguration" not in primary

    frame = wr.athena.read_sql_query(
        sql=MIXED_SQL,
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
        keep_files=True,
    )
    _assert_mixed_rows(frame)

    query_id = frame.query_metadata["QueryExecutionId"]
    assert frame.query_metadata["ResultConfiguration"][
        "OutputLocation"
    ].endswith(".csv")
    body = (
        consumer_harness.s3.get_object(
            Bucket=consumer_harness.bucket,
            Key=f"results/{query_id}.csv",
        )["Body"]
        .read()
        .decode("utf-8")
    )
    assert body == (
        '"one","ratio","amount","flag","day","ts","nothing"\n'
        '"1","1.5","12.34","True","2023-06-15",'
        '"2023-06-15 10:20:30.123",""\n'
    )
    assert str(frame["one"].dtype) == "Int32"
    assert str(frame["ratio"].dtype) == "float64"


def test_read_sql_query_api_path_managed_workgroup_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """FR-03/FR-20: managed workgroup serves rows inline via GetQueryResults."""
    workgroup = f"cs2b1-managed-{uuid.uuid4().hex}"
    consumer_harness.athena.create_work_group(
        Name=workgroup,
        Configuration={"ManagedQueryResultsConfiguration": {"Enabled": True}},
    )

    frame = wr.athena.read_sql_query(
        sql=MIXED_SQL,
        database=consumer_harness.database,
        ctas_approach=False,
        workgroup=workgroup,
    )
    _assert_mixed_rows(frame)

    execution = consumer_harness.athena.get_query_execution(
        QueryExecutionId=frame.query_metadata["QueryExecutionId"]
    )["QueryExecution"]
    assert execution["Status"]["State"] == "SUCCEEDED"
    # Managed runs report an empty ResultConfiguration member — no
    # OutputLocation anywhere in it — which is what makes wrangler fall back
    # to inline GetQueryResults reads for the workgroup.
    assert execution["ResultConfiguration"] == {}


def test_read_sql_query_cache_reuses_execution_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """FR-02: a second identical call reuses the first execution's artifacts.

    wrangler's cache probe walks ``list_query_executions`` +
    ``batch_get_query_execution`` (awswrangler/athena/_cache.py:113-129), so a
    hit proves those two ops report ``Query``/``StatementType``/timestamps
    faithfully; the hit then re-reads the recorded csv from the shared moto.
    """
    first = wr.athena.read_sql_query(
        sql=MIXED_SQL,
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
        athena_cache_settings=CACHE_SETTINGS,
    )
    first_id = first.query_metadata["QueryExecutionId"]

    second = wr.athena.read_sql_query(
        sql=MIXED_SQL,
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
        athena_cache_settings=CACHE_SETTINGS,
    )
    _assert_mixed_rows(second)
    assert second.query_metadata["QueryExecutionId"] == first_id

    executions = consumer_harness.athena.list_query_executions(
        WorkGroup="primary", MaxResults=10
    )["QueryExecutionIds"]
    assert executions == [first_id]


def test_read_sql_query_bad_sql_raises_shaped_error_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """FR-18: a parse error surfaces as the wrangler-recognizable 400."""
    with pytest.raises(botocore.exceptions.ClientError) as raised:
        wr.athena.read_sql_query(
            sql="SELECT FROM WHERE",
            database=consumer_harness.database,
            ctas_approach=False,
            s3_output=consumer_harness.prefix,
        )
    error = raised.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "Exception parsing query" in error["Message"]
