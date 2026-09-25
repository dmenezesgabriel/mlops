"""Shared live-stack machinery for the awswrangler consumer suites.

CS-2b1 (read path) and CS-2b2 (write path) both drive real awswrangler
3.17.1 through the emulator (in-process uvicorn, random port) against the
**compose moto container** as the shared data plane: the emulator's artifact
writer points at moto via its bridge IP (``ATHENA_LOCAL_MOTO_ENDPOINT_URL``),
Trino writes query results to the same moto internally (``moto:5000``), and
wrangler reads the artifacts back through an S3 client on that same moto — so
the csv/manifest/inline views observe one object store (the in-process
``LiveMotoServer`` is deliberately NOT used here; FR-06-style round-trips
would disagree on object identity).

Skip semantics mirror ``test_composition_root``: the suites skip when the
compose Trino coordinator or the bridge moto is unreachable, so a cold stack
never fails CI (the M5 compose stack is what the suite will pin instead).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

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
# The compose moto service publishes :5000 on the host; the env var overrides
# the default when moto is reached another way (e.g. inside mlops_net).
BRIDGE_URL_DEFAULT = "http://127.0.0.1:5000"

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


@dataclass
class ConsumerHarness:
    """Live stack endpoints: throwaway bucket + database on the shared moto."""

    athena: BaseClient
    s3: BaseClient
    glue: BaseClient
    bucket: str
    prefix: str
    database: str


@contextmanager
def consumer_harness_scope(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
    tag: str,
) -> Iterator[ConsumerHarness]:
    """Bind wrangler's boto3 session and the emulator to the live stack.

    Wrangler endpoint wiring is the FR-19 mechanism itself: per-service
    ``AWS_ENDPOINT_URL_ATHENA`` / ``AWS_ENDPOINT_URL_S3`` /
    ``AWS_ENDPOINT_URL_GLUE`` env vars on a boto3 session, so every client
    wrangler creates (athena, s3, glue) lands on the right host without
    explicit endpoint kwargs. The throwaway bucket and Glue database isolate
    each test on the shared moto (treated as user data: no resets).
    """
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
    bucket = f"athena-{tag}-{suffix}"
    database = f"{tag}_{suffix}"
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


def mixed_frame() -> pd.DataFrame:
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


def assert_mixed_rows(frame: pd.DataFrame) -> None:
    """Value equality for the mixed-type query, dtype-agnostic."""
    pd.testing.assert_frame_equal(
        frame.reset_index(drop=True), mixed_frame(), check_dtype=False
    )
