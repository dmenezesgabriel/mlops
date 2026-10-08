"""Result artifact writers (artifacts.py) per ADR-0007/0010.

The emulator owns artifact bytes; nothing is left to Trino's writer
(ADR-0006). These tests pin the exact files consumers read: ``{QueryID}.csv``
carries the quoted header row as line 1 because wrangler reads it with
``dtype`` keyed by column names and no ``names=``/``header=``
(awswrangler/athena/_read.py:225-238, s3/_read_text.py); ``{QueryID}.txt`` is
headerless (names are passed explicitly at _utils.py:200-213); the CTAS
manifest is one ``s3://`` path per line (_read.py:62-81). Files are written
before the SUCCEEDED transition, and a failed write keeps the execution FAILED
(ADR-0009 #4).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from athena_local.artifacts import ArtifactWriter, artifact_plan
from athena_local.common_schemas import ResultConfiguration
from athena_local.executions import ExecutionStore, QueryExecutionRecord
from athena_local.executor import ArtifactWriteError
from athena_local.output_targets import OutputSnapshot
from athena_local.s3_writer import S3Writer
from athena_local.trino_client import TrinoPage
from botocore.exceptions import EndpointConnectionError
from tests.unit._s3_fakes import RecordingObjectStore, s3_client_error

RESULT_LOCATION = "s3://results-bucket/analytics/"
CTAS_QUERY = (
    'CREATE TABLE "analytics"."t1" WITH (external_location = '
    "'s3://ctas-bucket/t1/', format = 'PARQUET') AS SELECT 1 AS a"
)

# A Trino-shaped engine query id: every data file a Trino 483 write lands
# carries it (hive `{qid}_{uuid}` / bucketed `0{b}_0_{uuid}_{qid}`, iceberg
# `{qid}-{uuid}`), which is what the manifest attribution keys on.
TRINO_QUERY_ID = "20261008_120000_00001_a1b2c3"

PLACEHOLDER_PAGE = TrinoPage(
    query_id=TRINO_QUERY_ID,  # manifest attribution keys on the engine id
    next_uri=None,
    update_type=None,
    columns=[],
    data=[],
    stats={},
    error=None,
)


def make_record(
    store: ExecutionStore,
    *,
    query: str,
    statement_type: str | None,
    substatement_type: str | None,
    columns: list[tuple[str, str]] | None = None,
    rows: list[list[object]] | None = None,
    output_location: str = RESULT_LOCATION,
    output_snapshot: OutputSnapshot | None = None,
    manifest_target_error: str | None = None,
) -> QueryExecutionRecord:
    record = store.create(
        query=query,
        workgroup="primary",
        database="analytics",
        result_configuration=ResultConfiguration(
            output_location=output_location
        ),
        statement_type=statement_type,
        substatement_type=substatement_type,
        output_snapshot=output_snapshot,
        manifest_target_error=manifest_target_error,
    )
    record.cache_result_page(
        columns if columns is not None else [],
        rows if rows is not None else [],
    )
    return record


def run(writer: ArtifactWriter, record: QueryExecutionRecord) -> None:
    """Drive the async write to completion, as the executor awaits it."""
    asyncio.run(writer.write(record, PLACEHOLDER_PAGE))


def test_select_writes_header_csv_and_sidecar() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="SELECT id, name FROM analytics.t",
        statement_type="DML",
        substatement_type="SELECT",
        columns=[("id", "integer"), ("name", "varchar")],
        rows=[[1, "alpha"], [2, "beta"]],
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    assert (
        store.bytes_of(f"{RESULT_LOCATION}{record.query_execution_id}.csv")
        == b'"id","name"\n"1","alpha"\n"2","beta"\n'
    )
    assert (
        f"{RESULT_LOCATION}{record.query_execution_id}.csv.metadata"
        in store.paths()
    )


def test_csv_null_escapes_and_embedded_delimiters() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="SELECT 1",
        statement_type="DML",
        substatement_type="SELECT",
        columns=[("a", "integer"), ("b", "varchar")],
        rows=[[None, 'say "hi"'], [7, "li,ke"]],
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    body = store.bytes_of(f"{RESULT_LOCATION}{record.query_execution_id}.csv")
    # QUOTE_ALL quotes every cell; the empty string stands for NULL and
    # embedded quotes are doubled, matching wrangler's csv.QUOTE_ALL read.
    assert body == b'"a","b"\n"","say ""hi"""\n"7","li,ke"\n'


def test_empty_select_writes_header_only() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="SELECT 1 WHERE FALSE",
        statement_type="DML",
        substatement_type="SELECT",
        columns=[("a", "integer")],
        rows=[],
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    assert (
        store.bytes_of(f"{RESULT_LOCATION}{record.query_execution_id}.csv")
        == b'"a"\n'
    )


def test_utility_writes_headerless_tab_txt_and_sidecar() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="DESCRIBE analytics.t",
        statement_type="UTILITY",
        substatement_type="DESCRIBE",
        columns=[("col_name", "varchar"), ("data_type", "varchar")],
        rows=[["id", "integer"], ["name", "varchar"]],
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    assert (
        store.bytes_of(f"{RESULT_LOCATION}{record.query_execution_id}.txt")
        == b'"id"\t"integer"\n"name"\t"varchar"\n'
    )
    assert (
        f"{RESULT_LOCATION}{record.query_execution_id}.txt.metadata"
        in store.paths()
    )


def test_ddl_non_ctas_classifies_as_txt() -> None:
    assert artifact_plan("DDL", "CREATE_TABLE").kind == "txt"
    assert artifact_plan("UTILITY", "DESCRIBE").kind == "txt"


def test_manifest_writes_ctas_files_and_sets_manifest_location() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_bbbb.parquet"): b"\0",
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_aaaa.parquet"): b"\0",
    }
    record = make_record(
        ExecutionStore(),
        query=CTAS_QUERY,
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_aaaa.parquet\n"
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_bbbb.parquet\n".encode()
    )
    assert record.data_manifest_location == manifest_path
    assert (
        f"{RESULT_LOCATION}{record.query_execution_id}.metadata"
        in store.paths()
    )


def test_ctas_without_external_location_fails_with_write_error() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="CREATE TABLE t AS SELECT 1 AS a",
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "external_location" in str(exc_info.value)


def test_ctas_manifest_ignores_quoted_identifier_shadow() -> None:
    # A quoted identifier or literal may textually contain
    # `external_location = '…'`; only the real WITH property may steer the
    # manifest — otherwise it would enumerate a foreign prefix's files.
    store = RecordingObjectStore()
    store.objects = {
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_aaaa.parquet"): b"\0",
        ("evil", "a.parquet"): b"\0",
    }
    record = make_record(
        ExecutionStore(),
        query=(
            "CREATE TABLE t (\"external_location = 's3://evil/'\") "
            "WITH (external_location='s3://ctas-bucket/t1/') AS SELECT 1"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_ctas_manifest_ignores_comment_literal_shadow() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_aaaa.parquet"): b"\0",
    }
    record = make_record(
        ExecutionStore(),
        query=(
            "CREATE TABLE t COMMENT 'external_location = ''s3://e/''' "
            "WITH (external_location='s3://ctas-bucket/t1/') AS SELECT 1"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_ctas_manifest_ignores_with_property_literal_shadow() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_aaaa.parquet"): b"\0",
    }
    record = make_record(
        ExecutionStore(),
        query=(
            "CREATE TABLE t WITH (comment = 'external_location = ''x''', "
            "external_location='s3://ctas-bucket/t1/') AS SELECT 1"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_ctas_unbalanced_with_fails_with_write_error() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query=(
            "CREATE TABLE t WITH (external_location='s3://ctas-bucket/t1/' "
            "AS SELECT 1"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "external_location" in str(exc_info.value)


def test_ctas_with_properties_without_external_location_fails() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="CREATE TABLE t WITH (format='PARQUET') AS SELECT 1",
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "external_location" in str(exc_info.value)


def test_ctas_identifier_ending_in_with_still_resolves() -> None:
    # `endswith` carries a "with" substring; the keyword boundary guard must
    # reject it without stopping the scan for the real WITH clause.
    store = RecordingObjectStore()
    store.objects = {
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_aaaa.parquet"): b"\0",
    }
    record = make_record(
        ExecutionStore(),
        query=(
            "CREATE TABLE endswith "
            "WITH (external_location='s3://ctas-bucket/t1/') AS SELECT 1"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_insert_manifest_lists_only_the_appended_files() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("data-bucket", "events/old-0.parquet"): b"old",
        ("data-bucket", f"events/{TRINO_QUERY_ID}_aaaa.parquet"): b"new",
        ("data-bucket", f"events/{TRINO_QUERY_ID}_bbbb.parquet"): b"new2",
    }
    record = make_record(
        ExecutionStore(),
        query="INSERT INTO analytics.events SELECT 1",
        statement_type="DML",
        substatement_type="INSERT",
        output_snapshot=OutputSnapshot(
            location="s3://data-bucket/events/",
            before_paths=frozenset({"s3://data-bucket/events/old-0.parquet"}),
        ),
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://data-bucket/events/{TRINO_QUERY_ID}_aaaa.parquet\n"
        f"s3://data-bucket/events/{TRINO_QUERY_ID}_bbbb.parquet\n".encode()
    )
    assert record.data_manifest_location == manifest_path


def test_unload_manifest_lists_only_the_appended_files() -> None:
    store = RecordingObjectStore()
    store.objects = {
        ("unload-bucket", f"out/{TRINO_QUERY_ID}_aaaa.parquet"): b"new",
        ("unload-bucket", f"out/{TRINO_QUERY_ID}_bbbb.parquet"): b"new2",
        ("unload-bucket", "out/old-0.parquet"): b"old",
    }
    record = make_record(
        ExecutionStore(),
        query=(
            "UNLOAD (SELECT * FROM analytics.t) "
            "TO 's3://unload-bucket/out/' WITH (format = 'PARQUET')"
        ),
        statement_type="DML",
        substatement_type="UNLOAD",
        output_snapshot=OutputSnapshot(
            location="s3://unload-bucket/out/",
            before_paths=frozenset({"s3://unload-bucket/out/old-0.parquet"}),
        ),
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://unload-bucket/out/{TRINO_QUERY_ID}_aaaa.parquet\n"
        f"s3://unload-bucket/out/{TRINO_QUERY_ID}_bbbb.parquet\n".encode()
    )


def test_insert_manifest_excludes_concurrent_writers_files() -> None:
    # The G-278 probe: a second writer landing files under the same target
    # prefix inside the submit→complete window must not be claimed by this
    # query's manifest — the engine query id stamped into Trino's file names
    # attributes each file to the run that wrote it.
    store = RecordingObjectStore()
    store.objects = {
        ("data-bucket", "events/old-0.parquet"): b"old",
        ("data-bucket", f"events/{TRINO_QUERY_ID}_aaaa.parquet"): b"a",
        (
            "data-bucket",
            "events/20261008_120000_00002_b9c8d7_bbbb.parquet",
        ): b"b",
        ("data-bucket", "events/stray.parquet"): b"stray",
    }
    record = make_record(
        ExecutionStore(),
        query="INSERT INTO analytics.events SELECT 1",
        statement_type="DML",
        substatement_type="INSERT",
        output_snapshot=OutputSnapshot(
            location="s3://data-bucket/events/",
            before_paths=frozenset({"s3://data-bucket/events/old-0.parquet"}),
        ),
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://data-bucket/events/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_manifest_attribution_accepts_all_trino_name_shapes() -> None:
    # Bucketed hive writes suffix the id (`0{b}_0_{uuid}_{qid}.ext`) and
    # iceberg joins it with a dash (`{qid}-{uuid}.ext`) — both still carry
    # this run's id, unlike the foreign file beside them.
    store = RecordingObjectStore()
    store.objects = {
        ("data-bucket", f"events/{TRINO_QUERY_ID}_aaaa.parquet"): b"a",
        (
            "data-bucket",
            f"events/000001_0_feed-{TRINO_QUERY_ID}.parquet",
        ): b"c",
        ("data-bucket", f"events/{TRINO_QUERY_ID}-beef.parquet"): b"d",
        (
            "data-bucket",
            "events/20261008_120000_00002_b9c8d7_bbbb.parquet",
        ): b"b",
    }
    record = make_record(
        ExecutionStore(),
        query="INSERT INTO analytics.events SELECT 1",
        statement_type="DML",
        substatement_type="INSERT",
        output_snapshot=OutputSnapshot(
            location="s3://data-bucket/events/", before_paths=frozenset()
        ),
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://data-bucket/events/000001_0_feed-{TRINO_QUERY_ID}.parquet\n"
        f"s3://data-bucket/events/{TRINO_QUERY_ID}-beef.parquet\n"
        f"s3://data-bucket/events/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_manifest_write_fails_when_engine_query_id_is_absent() -> None:
    # An unattributable manifest must fail the write instead of silently
    # over-claiming — an empty id would substring-match every file.
    store = RecordingObjectStore()
    store.objects = {
        ("data-bucket", "events/new-0.parquet"): b"new",
    }
    record = make_record(
        ExecutionStore(),
        query="INSERT INTO analytics.events SELECT 1",
        statement_type="DML",
        substatement_type="INSERT",
        output_snapshot=OutputSnapshot(
            location="s3://data-bucket/events/", before_paths=frozenset()
        ),
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        asyncio.run(
            writer.write(record, replace(PLACEHOLDER_PAGE, query_id=""))
        )

    assert "query id" in str(exc_info.value)


def test_ctas_manifest_excludes_foreign_files_in_the_location() -> None:
    # The CTAS listing path carries the same attribution contract: a file
    # under the target that lacks this run's id was not written by it —
    # including iceberg's id-less `metadata/` bookkeeping under the same
    # table location (a manifest lists data files, awswrangler reads them
    # as parquet).
    store = RecordingObjectStore()
    store.objects = {
        ("ctas-bucket", f"t1/{TRINO_QUERY_ID}_aaaa.parquet"): b"a",
        ("ctas-bucket", "t1/foreign.parquet"): b"foreign",
        (
            "ctas-bucket",
            "t1/metadata/00000-aaaa-1111.metadata.json",
        ): b"{}",
    }
    record = make_record(
        ExecutionStore(),
        query=CTAS_QUERY,
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    manifest_path = (
        f"{RESULT_LOCATION}{record.query_execution_id}-manifest.csv"
    )
    assert store.bytes_of(manifest_path) == (
        f"s3://ctas-bucket/t1/{TRINO_QUERY_ID}_aaaa.parquet\n".encode()
    )


def test_manifest_target_error_fails_the_write() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="INSERT INTO analytics.missing SELECT 1",
        statement_type="DML",
        substatement_type="INSERT",
        manifest_target_error=(
            "INSERT target table analytics.missing does not exist in the "
            "catalogue"
        ),
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "analytics.missing" in str(exc_info.value)


def test_missing_output_location_fails_with_write_error() -> None:
    store = RecordingObjectStore()
    record = ExecutionStore().create(
        query="SELECT 1",
        workgroup="primary",
        statement_type="DML",
        substatement_type="SELECT",
    )
    record.cache_result_page([("a", "integer")], [[1]])
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "OutputLocation" in str(exc_info.value)


def test_s3_put_failure_fails_the_write() -> None:
    store = RecordingObjectStore()
    store.put_error = s3_client_error("NoSuchBucket", "bucket missing")
    record = make_record(
        ExecutionStore(),
        query="SELECT 1",
        statement_type="DML",
        substatement_type="SELECT",
        columns=[("a", "integer")],
        rows=[[1]],
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "NoSuchBucket" in str(exc_info.value)


def test_metadata_sidecar_records_columns_and_row_count() -> None:
    store = RecordingObjectStore()
    record = make_record(
        ExecutionStore(),
        query="SELECT 1",
        statement_type="DML",
        substatement_type="SELECT",
        columns=[("id", "integer")],
        rows=[[1], [2]],
    )
    writer = ArtifactWriter(S3Writer(store))

    run(writer, record)

    body = store.bytes_of(
        f"{RESULT_LOCATION}{record.query_execution_id}.csv.metadata"
    )
    assert json.loads(body.decode("utf-8")) == {
        "columns": [{"Name": "id", "Type": "integer"}],
        "rows": 2,
    }


def test_s3_transport_failure_fails_the_write() -> None:
    store = RecordingObjectStore()
    store.put_error = EndpointConnectionError(endpoint_url="http://moto:5000")
    record = make_record(
        ExecutionStore(),
        query="SELECT 1",
        statement_type="DML",
        substatement_type="SELECT",
        columns=[("a", "integer")],
        rows=[[1]],
    )
    writer = ArtifactWriter(S3Writer(store))

    with pytest.raises(ArtifactWriteError) as exc_info:
        run(writer, record)

    assert "transport" in str(exc_info.value).lower()
