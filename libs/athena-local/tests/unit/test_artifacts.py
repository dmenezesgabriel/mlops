"""Result artifact writers (artifacts.py) per ADR-0007/0010 (AR-1).

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

import pytest
from athena_local.artifacts import ArtifactWriter, artifact_plan
from athena_local.common_schemas import ResultConfiguration
from athena_local.executions import ExecutionStore, QueryExecutionRecord
from athena_local.executor import ArtifactWriteError
from athena_local.s3_writer import S3Writer
from athena_local.trino_client import TrinoPage
from botocore.exceptions import EndpointConnectionError
from tests.unit._s3_fakes import RecordingObjectStore, s3_client_error

RESULT_LOCATION = "s3://results-bucket/analytics/"
CTAS_QUERY = (
    'CREATE TABLE "analytics"."t1" WITH (external_location = '
    "'s3://ctas-bucket/t1/', format = 'PARQUET') AS SELECT 1 AS a"
)

PLACEHOLDER_PAGE = TrinoPage(
    query_id="id",  # the writer reads the record's cached columns/rows
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
        ("ctas-bucket", "t1/part-00001-b.parquet"): b"\0",
        ("ctas-bucket", "t1/part-00000-a.parquet"): b"\0",
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
        b"s3://ctas-bucket/t1/part-00000-a.parquet\n"
        b"s3://ctas-bucket/t1/part-00001-b.parquet\n"
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
