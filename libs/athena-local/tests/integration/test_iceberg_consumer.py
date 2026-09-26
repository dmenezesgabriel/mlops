"""Iceberg write surface against the live data plane (awswrangler consumer).

``wr.athena.to_iceberg`` and ``wr.athena.delete_from_iceberg_table`` drive
the shapes this emulator's iceberg routing was built for: a
``TBLPROPERTIES('table_type'='ICEBERG')`` CREATE, a staged hive temp table,
``INSERT INTO iceberg SELECT``, then ``MERGE INTO … WHEN MATCHED THEN
DELETE`` (awswrangler/athena/_write_iceberg.py:108-113,411-426,871-877).
The Glue registration it leaves — ``Parameters.table_type=ICEBERG`` — is
what routes every later statement to the ``iceberg`` Trino catalog.
"""

from __future__ import annotations

from collections.abc import Iterator

import awswrangler as wr
import pandas as pd
import pytest
from tests.integration._consumer_harness import (
    ConsumerHarness,
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
        live_athena_server, monkeypatch, "ice"
    ) as harness:
        yield harness


def _iceberg_frame() -> pd.DataFrame:
    return pd.DataFrame({"id": [1, 2], "v": ["x", "y"]})


def test_to_iceberg_registers_and_inserts_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``to_iceberg`` creates the Iceberg table and lands the rows.

    The Glue registration is what later statements route on: moto must
    carry ``table_type=ICEBERG`` plus a ``StorageDescriptor.Location`` —
    Trino's Glue Iceberg catalog writes exactly that (probed).
    """
    table = "ice_write"
    wr.athena.to_iceberg(
        df=_iceberg_frame(),
        database=consumer_harness.database,
        table=table,
        temp_path=f"s3://{consumer_harness.bucket}/iceberg-tmp/",
        table_location=(f"s3://{consumer_harness.bucket}/iceberg/{table}/"),
        s3_output=consumer_harness.prefix,
    )

    glue_table = consumer_harness.glue.get_table(
        DatabaseName=consumer_harness.database, Name=table
    )["Table"]
    assert glue_table["Parameters"]["table_type"] == "ICEBERG"
    assert glue_table["StorageDescriptor"]["Location"].rstrip("/") == (
        f"s3://{consumer_harness.bucket}/iceberg/{table}"
    )

    # Plain SELECT routes to the iceberg catalog on the same Glue marker —
    # the hive catalog would fail UNSUPPORTED_TABLE_TYPE.
    frame = wr.athena.read_sql_query(
        sql=f'SELECT * FROM "{table}" ORDER BY "id"',
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert frame["id"].tolist() == [1, 2]
    assert frame["v"].tolist() == ["x", "y"]

    # wrangler drops the staging table in a finally; only the Iceberg
    # table remains in the database.
    names = [
        entry["Name"]
        for entry in consumer_harness.glue.get_tables(
            DatabaseName=consumer_harness.database
        )["TableList"]
    ]
    assert names == [table]


def test_delete_from_iceberg_table_merges_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """``delete_from_iceberg_table`` stages delete keys and merge-deletes.

    The wire MERGE qualifies only the Iceberg target — the staged hive temp
    table stays session-catalog relative — and leaves one row behind.
    """
    table = "ice_delete"
    wr.athena.to_iceberg(
        df=_iceberg_frame(),
        database=consumer_harness.database,
        table=table,
        temp_path=f"s3://{consumer_harness.bucket}/iceberg-tmp/",
        table_location=(f"s3://{consumer_harness.bucket}/iceberg/{table}/"),
        s3_output=consumer_harness.prefix,
    )

    wr.athena.delete_from_iceberg_table(
        df=pd.DataFrame({"id": [1]}),
        database=consumer_harness.database,
        table=table,
        merge_cols=["id"],
        temp_path=f"s3://{consumer_harness.bucket}/iceberg-del-tmp/",
        s3_output=consumer_harness.prefix,
    )

    frame = wr.athena.read_sql_query(
        sql=f'SELECT * FROM "{table}" ORDER BY "id"',
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert frame["id"].tolist() == [2]
    assert frame["v"].tolist() == ["y"]

    names = [
        entry["Name"]
        for entry in consumer_harness.glue.get_tables(
            DatabaseName=consumer_harness.database
        )["TableList"]
    ]
    assert names == [table]


def test_to_iceberg_appends_to_existing_table_live(
    consumer_harness: ConsumerHarness,
) -> None:
    """A second ``to_iceberg`` skips CREATE and INSERTs into the table."""
    table = "ice_append"
    # temp_path is the staging dataset's own location: reusing one across
    # calls makes the second INSERT read the first call's files too
    # (wrangler leaves them when keep_files=True).
    for index, frame in enumerate(
        (
            pd.DataFrame({"id": [1], "v": ["x"]}),
            pd.DataFrame({"id": [2], "v": ["y"]}),
        )
    ):
        wr.athena.to_iceberg(
            df=frame,
            database=consumer_harness.database,
            table=table,
            temp_path=f"s3://{consumer_harness.bucket}/iceberg-tmp-{index}/",
            table_location=(
                f"s3://{consumer_harness.bucket}/iceberg/{table}/"
            ),
            s3_output=consumer_harness.prefix,
        )

    frame = wr.athena.read_sql_query(
        sql=f'SELECT * FROM "{table}" ORDER BY "id"',
        database=consumer_harness.database,
        ctas_approach=False,
        s3_output=consumer_harness.prefix,
    )
    assert frame["id"].tolist() == [1, 2]
