"""UNLOAD consumer suite against the live data plane.

awswrangler's two UNLOAD surfaces — ``read_sql_query(unload_approach=True)``
and ``wr.athena.unload`` — submit Athena's ``UNLOAD (q) TO 's3://…' WITH
(props)`` vocabulary (awswrangler/athena/_read.py:783-791), which Trino's
grammar lacks outright. The emulator rewrites it to a CTAS writing the TO
path through a generated temp table whose Glue entry is deleted when the
statement ends, because real UNLOAD registers no catalog table (dialect.py).
These tests pin the end-to-end consumer result — manifest → parquet read,
``partitioned_by`` hive dirs, the ``compression`` session property — plus
the cleanup, on the shared compose moto exactly like the other CS suites.
"""

from __future__ import annotations

from collections.abc import Iterator

import awswrangler as wr
import pytest
from tests.integration._consumer_harness import (
    MIXED_SQL,
    ConsumerHarness,
    assert_mixed_rows,
    consumer_harness_scope,
)
from tests.integration.conftest import LiveAthenaServer


@pytest.fixture()
def consumer_harness(
    live_athena_server: LiveAthenaServer,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[ConsumerHarness]:
    """Bind wrangler's boto3 session and the emulator to the live stack."""
    with consumer_harness_scope(
        live_athena_server, monkeypatch, "unload"
    ) as harness:
        yield harness


def test_read_sql_query_unload_approach_reads_parquet_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """The wrangler read path the gap measured: UNLOAD → manifest → parquet.

    ``_unload`` sends ``UNLOAD (sql) TO '{s3_output}' WITH (format='PARQUET')``
    then ``_fetch_parquet_result`` reads the files the manifest lists
    (_read.py:150-156); ``keep_files=False`` deletes them afterwards.
    """
    frame = wr.athena.read_sql_query(
        sql=MIXED_SQL,
        database=consumer_harness.database,
        ctas_approach=False,
        unload_approach=True,
        s3_output=consumer_harness.prefix,
        unload_parameters={"file_format": "PARQUET"},
    )

    assert_mixed_rows(frame)
    assert _temp_tables(consumer_harness) == []


def test_unload_approach_compression_reaches_the_writer_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``compression='snappy'`` travels as ``hive.compression_codec``.

    The hive connector takes the write codec as a session property, not a
    CTAS table property; this round-trip only succeeds if the
    ``X-Trino-Session`` header applied the codec Trino-side (pyarrow reads
    snappy transparently, so the read-back proves the write worked).
    """
    frame = wr.athena.read_sql_query(
        sql="SELECT 1 AS one, 'alpha' AS label",
        database=consumer_harness.database,
        ctas_approach=False,
        unload_approach=True,
        s3_output=consumer_harness.prefix,
        unload_parameters={
            "file_format": "PARQUET",
            "compression": "snappy",
        },
    )

    assert frame.shape == (1, 2)
    assert frame.iloc[0].tolist() == [1, "alpha"]


def test_athena_unload_writes_files_and_leaves_no_table_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``wr.athena.unload`` lands parquet at TO and drops the temp table.

    The manifest names exactly the files the query wrote (the snapshot diff
    also written for INSERT); real UNLOAD registers no catalog entry, so
    ``athena_unload_*`` must be gone from Glue once the execution ends.
    """
    metadata = wr.athena.unload(
        sql="SELECT * FROM (VALUES (1,'a'),(2,'b')) t(n,s)",
        path=f"s3://{consumer_harness.bucket}/unload/",
        database=consumer_harness.database,
    )

    keys = _list_keys(consumer_harness, "unload/")
    manifest_keys = [key for key in keys if key.endswith("-manifest.csv")]
    assert len(manifest_keys) == 1
    assert metadata.manifest_location is not None
    assert metadata.manifest_location.endswith(manifest_keys[0])
    manifest = consumer_harness.s3.get_object(
        Bucket=consumer_harness.bucket, Key=manifest_keys[0]
    )["Body"].read()
    data_paths = manifest.decode().split()
    # The manifest lists only the query's own files — the -manifest.csv and
    # .metadata sidecars it shares the prefix with are never entries.
    assert data_paths
    listed = {f"s3://{consumer_harness.bucket}/{key}" for key in keys}
    assert set(data_paths) < listed
    assert _temp_tables(consumer_harness) == []


def test_unload_partitioned_by_writes_hive_directories_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``partitioned_by`` maps verbatim: Trino writes ``key=value/`` dirs."""
    wr.athena.unload(
        sql="SELECT 1 AS n, 'EU' AS region",
        path=f"s3://{consumer_harness.bucket}/partitioned/",
        database=consumer_harness.database,
        partitioned_by=["region"],
    )

    keys = _list_keys(consumer_harness, "partitioned/region=EU/")
    assert keys
    assert _temp_tables(consumer_harness) == []


def test_unload_to_a_nonempty_location_fails_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """A second UNLOAD to the same path fails like Athena's nonempty-target
    rejection, and the failed CTAS's temp table is still cleaned up.
    """
    sql = "SELECT 1 AS n"
    path = f"s3://{consumer_harness.bucket}/occupied/"
    wr.athena.unload(sql=sql, path=path, database=consumer_harness.database)

    with pytest.raises(wr.exceptions.QueryFailed):
        wr.athena.unload(
            sql=sql, path=path, database=consumer_harness.database
        )

    assert _temp_tables(consumer_harness) == []


def test_unload_duplicate_column_names_map_to_invalid_argument_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Trino's CTAS dup-column message carries Athena's expected wording.

    ``_unload`` re-raises ``QueryFailed`` as ``InvalidArgumentValue`` when
    the reason names a duplicated column (_read.py:822-825); Trino's own
    ``Column name 'x' specified more than once`` satisfies that grep, so the
    consumer sees the same error class real AWS produces.
    """
    with pytest.raises(wr.exceptions.InvalidArgumentValue):
        wr.athena.unload(
            sql="SELECT 1 AS dup, 2 AS dup",
            path=f"s3://{consumer_harness.bucket}/dup/",
            database=consumer_harness.database,
        )

    assert _temp_tables(consumer_harness) == []


def _list_keys(harness: ConsumerHarness, prefix: str) -> set[str]:
    """Object keys under ``prefix`` in the throwaway bucket."""
    response = harness.s3.list_objects_v2(Bucket=harness.bucket, Prefix=prefix)
    return {item["Key"] for item in response.get("Contents", [])}


def _temp_tables(harness: ConsumerHarness) -> list[str]:
    """Leftover emulator temp tables in the throwaway database."""
    response = harness.glue.get_tables(DatabaseName=harness.database)
    return [
        table["Name"]
        for table in response.get("TableList", [])
        if table["Name"].startswith("athena_unload_")
    ]
