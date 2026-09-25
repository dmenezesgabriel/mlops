"""awswrangler write-path consumer suite against the live data plane.

The write-path acceptance slice: a prepared statement created over the wire
then run as a bare ``EXECUTE "name"`` whose values arrive as
``StartQueryExecution.ExecutionParameters`` (wrangler ``params`` +
``paramstyle="qmark"``, awswrangler/tests/unit/test_athena_prepared.py:
174-183), the direct ``?``-marker query path, the ``to_parquet`` CTAS
round-trip (``read_sql_query(ctas_approach=True)``: manifest → parquet
read-back through ``Statistics.DataManifestLocation``,
awswrangler/athena/_read.py:62-81,135-206), CTAS combined with qmark values,
and the parameter-count-mismatch FAILED execution.

Binding semantics follow real Athena's typed execution parameters: a bare
value like ``"Washington"`` substitutes as a string literal while ``"1"``
and ``DATE '2020-01-01'`` travel as their typed literals — wrangler's own
real-AWS distributed suite pins exactly these spellings
(awswrangler/tests/unit/test_athena.py:936-937).
"""

from __future__ import annotations

import re
import uuid
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
        live_athena_server, monkeypatch, "cs2b2"
    ) as harness:
        yield harness


def test_prepared_statement_execute_with_qmark_params_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Bare ``EXECUTE "name"`` + ExecutionParameters binds values.

    ``create_prepared_statement`` probes ``get_prepared_statement`` first and
    must see the RNFE for a fresh name (wrangler _statements.py:26-29
    policy); the stored ``?`` query then runs with the raw value wrangler
    shipped as ``ExecutionParameters``.
    """
    statement = f"ps_{uuid.uuid4().hex}"
    wr.athena.create_prepared_statement(
        sql=(
            "SELECT * FROM (VALUES ('Washington', 'Seattle', 42), "
            "('Denver', 'Chicago', 7)) AS t(origin, dest, code) "
            "WHERE origin = ?"
        ),
        statement_name=statement,
        workgroup="primary",
    )

    frame = wr.athena.read_sql_query(
        sql=f'EXECUTE "{statement}"',
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
        params=["Washington"],
        paramstyle="qmark",
    )
    assert frame.shape == (1, 3)
    assert frame.iloc[0]["dest"] == "Seattle"
    assert int(frame.iloc[0]["code"]) == 42

    execution = consumer_harness.athena.get_query_execution(
        QueryExecutionId=frame.query_metadata["QueryExecutionId"]
    )["QueryExecution"]
    assert execution["Status"]["State"] == "SUCCEEDED"
    # The wire Query keeps the submitted EXECUTE text (never the bound SQL)
    # and reports the raw parameters, exactly like real Athena.
    assert execution["Query"] == f'EXECUTE "{statement}"'
    assert execution["ExecutionParameters"] == ["Washington"]
    assert execution["StatementType"] == "DML"
    assert execution["SubstatementType"] == "SELECT"


def test_read_sql_query_qmark_params_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """A ``?``-marker query binds ExecutionParameters server-side."""
    frame = wr.athena.read_sql_query(
        sql=(
            "SELECT * FROM (VALUES ('Washington', 'Seattle'), "
            "('Denver', 'Chicago')) AS t(origin, dest) WHERE origin = ?"
        ),
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
        params=["Denver"],
        paramstyle="qmark",
    )
    assert frame.shape == (1, 2)
    assert frame.iloc[0]["dest"] == "Chicago"

    execution = consumer_harness.athena.get_query_execution(
        QueryExecutionId=frame.query_metadata["QueryExecutionId"]
    )["QueryExecution"]
    assert execution["Status"]["State"] == "SUCCEEDED"
    assert "WHERE origin = ?" in execution["Query"]
    assert execution["ExecutionParameters"] == ["Denver"]
    assert execution["StatementType"] == "DML"


def test_read_sql_query_ctas_parquet_round_trip_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``to_parquet`` CTAS reads back through the data manifest.

    ``Statistics.DataManifestLocation`` names a same-bucket manifest
    (wrangler refuses cross-bucket manifests, _read.py:74-79) whose entries
    are exactly the data files the CTAS wrote under its ``external_location``
    — the manifest → parquet read-back is what returns the frame. The Glue
    temp table itself cannot be asserted post-hoc: wrangler drops it in an
    unconditional ``finally`` (``catalog.delete_table_if_exists`` in
    ``_resolve_query_without_cache``, _read.py), ``keep_files`` only governs
    the S3 objects.
    """
    frame = wr.athena.read_sql_query(
        sql=MIXED_SQL,
        database=consumer_harness.database,
        ctas_approach=True,
        s3_output=consumer_harness.prefix,
        keep_files=True,
    )
    assert_mixed_rows(frame)

    manifest = frame.query_metadata["Statistics"]["DataManifestLocation"]
    assert manifest is not None
    assert manifest.endswith("-manifest.csv")
    assert manifest.startswith(f"s3://{consumer_harness.bucket}/")

    # The wire Query pins the CTAS template wrangler generated
    # (awswrangler/athena/_utils.py:842-863): the temp table name and its
    # external_location must be exactly where the manifest lists files.
    wire_query = consumer_harness.athena.get_query_execution(
        QueryExecutionId=frame.query_metadata["QueryExecutionId"]
    )["QueryExecution"]["Query"]
    table_match = re.search(
        r'CREATE TABLE "(?P<database>[^"]+)"\.'
        r'"(?P<table>[^"]+)"',
        wire_query,
    )
    assert table_match is not None
    assert table_match.group("database") == consumer_harness.database
    table_name = table_match.group("table")
    expected_location = f"{consumer_harness.prefix}{table_name}"

    manifest_key = "/".join(manifest.removeprefix("s3://").split("/")[1:])
    body = (
        consumer_harness.s3.get_object(
            Bucket=consumer_harness.bucket, Key=manifest_key
        )["Body"]
        .read()
        .decode("utf-8")
    )
    paths = [line for line in body.splitlines() if line]
    assert paths, "manifest must list the data files the CTAS wrote"
    for path in paths:
        assert path.startswith(f"{expected_location}/")
        assert path != manifest

    # keep_files=True leaves the data files on moto: the manifest and the
    # object listing must agree, proving one shared object store.
    listing = consumer_harness.s3.list_objects_v2(
        Bucket=consumer_harness.bucket, Prefix=f"results/{table_name}"
    )["Contents"]
    object_paths = {
        f"s3://{consumer_harness.bucket}/{item['Key']}" for item in listing
    }
    assert set(paths) == object_paths


def test_create_ctas_table_registers_glue_table_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """The CTAS template registers a Glue table in the harness DB.

    ``wr.athena.create_ctas_table`` (the template ``read_sql_query`` runs
    internally, but without the read-back drop, _read.py) leaves the table,
    so its live write path is visible: Trino created it in the harness
    database with the ``external_location`` the ``WITH(...)`` clause named.
    """
    result = wr.athena.create_ctas_table(
        sql="SELECT CAST(42 AS INTEGER) AS one",
        database=consumer_harness.database,
        s3_output=consumer_harness.prefix,
        wait=True,
    )
    table_name = str(result["ctas_table"])
    table = consumer_harness.glue.get_table(
        DatabaseName=consumer_harness.database, Name=table_name
    )["Table"]
    expected_location = f"{consumer_harness.prefix}{table_name}"
    assert table["StorageDescriptor"]["Location"] == expected_location

    metadata = result["ctas_query_metadata"]
    assert metadata.manifest_location == (
        f"{consumer_harness.prefix}{metadata.execution_id}-manifest.csv"
    )

    manifest_key = "/".join(
        metadata.manifest_location.removeprefix("s3://").split("/")[1:]
    )
    body = (
        consumer_harness.s3.get_object(
            Bucket=consumer_harness.bucket, Key=manifest_key
        )["Body"]
        .read()
        .decode("utf-8")
    )
    paths = [line for line in body.splitlines() if line]
    for path in paths:
        assert path.startswith(f"{expected_location}/")

    consumer_harness.glue.delete_table(
        DatabaseName=consumer_harness.database, Name=table_name
    )


def test_read_sql_query_ctas_with_qmark_params_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """Qmark values bind inside the CTAS body, then read back.

    wrangler wraps the ``?``-bearing SQL in the CTAS template and ships the
    values as ``ExecutionParameters``; the emulator binds the marker inside
    the DDL before Trino submits it (wrangler's "ctas" distributed param set,
    test_athena.py:932).
    """
    frame = wr.athena.read_sql_query(
        sql=(
            "SELECT * FROM (VALUES (1, 'a'), (2, 'b')) AS t(one, two) "
            "WHERE one = ?"
        ),
        database=consumer_harness.database,
        ctas_approach=True,
        s3_output=consumer_harness.prefix,
        params=["2"],
        paramstyle="qmark",
    )
    assert frame.shape == (1, 2)
    assert int(frame.iloc[0]["one"]) == 2
    assert frame.iloc[0]["two"] == "b"


def test_read_sql_query_qmark_count_mismatch_is_failed_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """A parameter-count mismatch is a FAILED execution, never a 400.

    wrangler waits on the execution and surfaces the emulator's
    StateChangeReason through its QueryFailed exception; the request itself
    answered 200 with an execution ID (real Athena fails these, it does not
    reject them).
    """
    with pytest.raises(wr.exceptions.QueryFailed) as raised:
        wr.athena.read_sql_query(
            sql=(
                "SELECT * FROM (VALUES ('a'), ('b')) AS t(origin) "
                "WHERE origin = ?"
            ),
            database=consumer_harness.database,
            ctas_approach=False,
            s3_output=consumer_harness.prefix,
            params=["a", "b"],
            paramstyle="qmark",
        )
    assert "Incorrect number of parameters: expected 1 but found 2" in str(
        raised.value
    )
