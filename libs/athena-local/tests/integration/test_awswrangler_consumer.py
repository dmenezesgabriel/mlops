"""awswrangler read-path consumer suite against the live data plane.

Drives real awswrangler 3.17.1 through the emulator (in-process uvicorn,
random port) and the **compose moto container** as the shared data plane: the
emulator's artifact writer points at moto via its bridge IP
(``ATHENA_LOCAL_MOTO_ENDPOINT_URL``), Trino writes query results to the same
moto internally (``moto:5000``), and wrangler reads the artifacts back through
an S3 client on that same moto — so the CSV/cache/inline views observe one
object store (this is why the in-process ``LiveMotoServer`` is deliberately
NOT used here; a CTAS round-trip would disagree on object identity).

Skip semantics mirror ``test_composition_root``: the suite skips when the
compose Trino coordinator or the bridge moto is unreachable, so a cold stack
never fails CI (the compose stack pins the deployed service separately).

Wrangler endpoint routing rides on per-service
``AWS_ENDPOINT_URL_ATHENA`` / ``AWS_ENDPOINT_URL_S3`` / ``AWS_ENDPOINT_URL_GLUE``
env vars on a boto3 session, so every client wrangler creates (athena, s3, glue)
lands on the right host without explicit endpoint kwargs.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import awswrangler as wr
import botocore.exceptions
import pytest
from tests.integration._consumer_harness import (
    MIXED_SQL,
    ConsumerHarness,
    assert_mixed_rows,
    consumer_harness_scope,
)
from tests.integration.conftest import LiveAthenaServer

CACHE_SETTINGS = {"max_cache_seconds": 90}


@pytest.fixture()
def consumer_harness(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[ConsumerHarness]:
    """Bind wrangler's boto3 session and the emulator to the live stack."""
    with consumer_harness_scope(
        live_athena_server, monkeypatch, "cs2b1"
    ) as harness:
        yield harness


def test_read_sql_query_csv_path_round_trips_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Default non-managed ``primary`` reads the csv artifact back."""
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
    assert_mixed_rows(frame)

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
    """A managed workgroup serves rows inline via GetQueryResults."""
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
    assert_mixed_rows(frame)

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
    """A second identical call reuses the first execution's artifacts.

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
    assert_mixed_rows(second)
    assert second.query_metadata["QueryExecutionId"] == first_id

    executions = consumer_harness.athena.list_query_executions(
        WorkGroup="primary", MaxResults=10
    )["QueryExecutionIds"]
    assert executions == [first_id]


def test_read_sql_query_bad_sql_raises_shaped_error_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """A parse error surfaces as the wrangler-recognizable 400."""
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
