"""INSERT/UNLOAD manifest target parsing and capture.

The manifest must list exactly the files a query wrote. Trino's statement
protocol never reports written file paths and an existing table's location
already holds files from earlier writes, so ``OutputSnapshotter`` resolves
where an INSERT/UNLOAD writes and captures the object list before the
statement is submitted; the artifact writer emits the after-minus-before diff.
These tests pin the parsers on real query text and the capture on the shipped
boundaries (GlueProxy + S3Writer) over their named fakes.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.glue_proxy import GlueProxy
from athena_local.output_targets import (
    ManifestTargetError,
    OutputSnapshot,
    OutputSnapshotter,
    insert_table_reference,
    unload_location,
)
from athena_local.s3_writer import S3Writer
from tests.unit._glue_fakes import FakeGlueClient
from tests.unit._s3_fakes import RecordingObjectStore

INSERT_TABLE: dict[str, object] = {
    "Name": "events",
    "TableType": "EXTERNAL_TABLE",
    "StorageDescriptor": {
        "Columns": [{"Name": "id", "Type": "int"}],
        "Location": "s3://data-bucket/events/",
    },
}


def test_insert_reference_qualified() -> None:
    reference = insert_table_reference(
        "INSERT INTO analytics.events SELECT * FROM src"
    )

    assert reference == ("analytics", "events")


def test_insert_reference_catalog_qualified_keeps_database() -> None:
    reference = insert_table_reference(
        'INSERT INTO "mycat"."analytics"."events" SELECT 1'
    )

    assert reference == ("analytics", "events")


def test_insert_reference_quoted_identifiers() -> None:
    reference = insert_table_reference(
        'INSERT INTO "analytics"."event log" VALUES (1)'
    )

    assert reference == ("analytics", "event log")


def test_insert_reference_partition_clause() -> None:
    reference = insert_table_reference(
        "INSERT INTO analytics.events PARTITION (dt = '2024-01-01') "
        "SELECT * FROM src"
    )

    assert reference == ("analytics", "events")


def test_insert_reference_survives_comments() -> None:
    reference = insert_table_reference(
        "-- header comment\nINSERT INTO analytics.events -- trailing\nSELECT 1"
    )

    assert reference == ("analytics", "events")


def test_insert_reference_lowers_unquoted_identifiers() -> None:
    reference = insert_table_reference("INSERT INTO ANALYTICS.Events SELECT 1")

    assert reference == ("analytics", "events")


def test_insert_reference_overwrite_is_none() -> None:
    assert (
        insert_table_reference("INSERT OVERWRITE analytics.events SELECT 1")
        is None
    )


def test_insert_reference_non_insert_is_none() -> None:
    assert insert_table_reference("SELECT * FROM events") is None


def test_insert_reference_missing_into_is_none() -> None:
    assert insert_table_reference("INSERT events SELECT 1") is None


def test_unload_location_basic() -> None:
    location = unload_location(
        "UNLOAD (SELECT * FROM events) TO 's3://unload-bucket/out/' "
        "WITH (format = 'PARQUET')"
    )

    assert location == "s3://unload-bucket/out/"


def test_unload_location_case_and_whitespace() -> None:
    location = unload_location(
        "unload (select 1)  to  's3://unload-bucket/out2/' with (format='ORC')"
    )

    assert location == "s3://unload-bucket/out2/"


def test_unload_location_escaped_quote() -> None:
    location = unload_location(
        "UNLOAD (SELECT * FROM t) TO 's3://unload-bucket/it''s/' "
        "WITH (format = 'PARQUET')"
    )

    assert location == "s3://unload-bucket/it's/"


def test_unload_location_ignores_subquery_string() -> None:
    location = unload_location(
        "UNLOAD (SELECT 'see to ' || 'x') TO 's3://unload-bucket/real/' "
        "WITH (format = 'PARQUET')"
    )

    assert location == "s3://unload-bucket/real/"


def test_unload_location_ignores_subquery_text() -> None:
    location = unload_location(
        "UNLOAD (SELECT content FROM t WHERE note = 'to here') "
        "TO 's3://unload-bucket/real/' WITH (format = 'PARQUET')"
    )

    assert location == "s3://unload-bucket/real/"


def test_unload_location_missing_to_is_none() -> None:
    assert unload_location("UNLOAD (SELECT * FROM events)") is None


def test_unload_location_non_unload_is_none() -> None:
    assert unload_location("SELECT 'UNLOAD' AS kind") is None


def capture(
    snapshotter: OutputSnapshotter,
    *,
    query: str,
    database: str | None = None,
    catalog: str | None = None,
    substatement_type: str | None = None,
) -> OutputSnapshot | None:
    """Drive the async ``capture`` from a synchronous test."""

    async def run() -> OutputSnapshot | None:
        return await snapshotter.capture(
            query, database, catalog, substatement_type
        )

    return asyncio.run(run())


def snapshotter_with(
    tables: dict[str, list[dict[str, object]]] | None = None,
    objects: dict[tuple[str, str], bytes] | None = None,
) -> tuple[OutputSnapshotter, RecordingObjectStore]:
    store = RecordingObjectStore()
    store.objects = dict(objects) if objects is not None else {}
    snapshotter = OutputSnapshotter(
        GlueProxy(FakeGlueClient(tables=tables)), S3Writer(store)
    )
    return snapshotter, store


def test_capture_insert_lists_the_table_location() -> None:
    snapshotter, _store = snapshotter_with(
        tables={"analytics": [INSERT_TABLE]},
        objects={
            ("data-bucket", "events/old-0.parquet"): b"old",
            ("data-bucket", "events/part-0.parquet"): b"new",
        },
    )

    snapshot = capture(
        snapshotter,
        query="INSERT INTO analytics.events SELECT 1",
        database="analytics",
        substatement_type="INSERT",
    )

    assert snapshot == OutputSnapshot(
        location="s3://data-bucket/events/",
        before_paths=frozenset(
            {
                "s3://data-bucket/events/old-0.parquet",
                "s3://data-bucket/events/part-0.parquet",
            }
        ),
    )


def test_capture_insert_defaults_database_from_context() -> None:
    snapshotter, _store = snapshotter_with(
        tables={"analytics": [INSERT_TABLE]}
    )

    snapshot = capture(
        snapshotter,
        query="INSERT INTO events SELECT 1",
        database="analytics",
        substatement_type="INSERT",
    )

    assert snapshot is not None
    assert snapshot.location == "s3://data-bucket/events/"


def test_capture_insert_missing_database_is_a_target_error() -> None:
    snapshotter, _store = snapshotter_with(
        tables={"analytics": [INSERT_TABLE]}
    )

    with pytest.raises(ManifestTargetError) as exc_info:
        capture(
            snapshotter,
            query="INSERT INTO events SELECT 1",
            database=None,
            substatement_type="INSERT",
        )

    assert "database" in str(exc_info.value)


def test_capture_insert_missing_table_is_a_target_error() -> None:
    snapshotter, _store = snapshotter_with(tables={"analytics": []})

    with pytest.raises(ManifestTargetError) as exc_info:
        capture(
            snapshotter,
            query="INSERT INTO analytics.events SELECT 1",
            database="analytics",
            substatement_type="INSERT",
        )

    assert "events" in str(exc_info.value)


def test_capture_insert_table_without_location_is_a_target_error() -> None:
    table_without_location = {
        "Name": "events",
        "StorageDescriptor": {"Columns": [{"Name": "id", "Type": "int"}]},
    }
    snapshotter, _store = snapshotter_with(
        tables={"analytics": [table_without_location]}
    )

    with pytest.raises(ManifestTargetError) as exc_info:
        capture(
            snapshotter,
            query="INSERT INTO analytics.events SELECT 1",
            database="analytics",
            substatement_type="INSERT",
        )

    assert "location" in str(exc_info.value)


def test_capture_unload_lists_the_to_location() -> None:
    snapshotter, _store = snapshotter_with(
        objects={
            ("unload-bucket", "out/part-0.parquet"): b"new",
            ("unload-bucket", "out/old.parquet"): b"old",
        }
    )

    snapshot = capture(
        snapshotter,
        query=(
            "UNLOAD (SELECT * FROM events) TO 's3://unload-bucket/out/' "
            "WITH (format = 'PARQUET')"
        ),
        substatement_type="UNLOAD",
    )

    assert snapshot == OutputSnapshot(
        location="s3://unload-bucket/out/",
        before_paths=frozenset(
            {
                "s3://unload-bucket/out/part-0.parquet",
                "s3://unload-bucket/out/old.parquet",
            }
        ),
    )


def test_capture_unload_without_to_is_a_target_error() -> None:
    snapshotter, _store = snapshotter_with()

    with pytest.raises(ManifestTargetError) as exc_info:
        capture(
            snapshotter,
            query="UNLOAD (SELECT * FROM events)",
            substatement_type="UNLOAD",
        )

    assert "TO" in str(exc_info.value)


def test_capture_skips_statements_without_a_manifest() -> None:
    snapshotter, store = snapshotter_with(tables={"analytics": [INSERT_TABLE]})

    for classification in ("SELECT", "CREATE_TABLE_AS_SELECT", "DESCRIBE"):
        snapshot = capture(
            snapshotter,
            query="SELECT 1",
            database="analytics",
            substatement_type=classification,
        )
        assert snapshot is None
        assert store.list_calls == []
