"""Step definitions for the result-artifacts BDD feature (AR-1).

Steps drive the shipped boundary — a real ``ArtifactWriter`` over a real
``S3Writer`` on the named ``RecordingObjectStore`` fake — so the feature pins
the byte contract consumers depend on without HTTP, moto, or docker
(F.I.R.S.T., mirroring the workgroup BDD harness).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import pytest
from athena_local.artifacts import ArtifactWriter
from athena_local.common_schemas import ResultConfiguration
from athena_local.executions import ExecutionStore, QueryExecutionRecord
from athena_local.output_targets import OutputSnapshot
from athena_local.s3_writer import S3Writer
from athena_local.trino_client import TrinoPage
from pytest_bdd import given, parsers, scenarios, then, when
from tests.unit._s3_fakes import RecordingObjectStore

scenarios("artifacts.feature")

PLACEHOLDER_PAGE = TrinoPage(
    query_id="id",  # the writer reads the record's cached columns/rows
    next_uri=None,
    update_type=None,
    columns=[],
    data=[],
    stats={},
    error=None,
)


@dataclass
class ArtifactOutcome:
    """State shared between the when and then steps of a scenario."""

    store: RecordingObjectStore = field(default_factory=RecordingObjectStore)
    result_location: str = ""
    columns: list[tuple[str, str]] = field(default_factory=list)
    rows: list[list[object]] = field(default_factory=list)
    record: QueryExecutionRecord | None = None
    appended_paths: list[str] = field(default_factory=list)

    def persist(self) -> None:
        assert self.record is not None
        asyncio.run(
            ArtifactWriter(S3Writer(self.store)).write(
                self.record, PLACEHOLDER_PAGE
            )
        )


@pytest.fixture
def outcome() -> ArtifactOutcome:
    return ArtifactOutcome()


@given(
    'a fresh object store and a result location "s3://results-bucket/analytics/"'
)
def _fresh_store(outcome: ArtifactOutcome) -> None:
    outcome.result_location = "s3://results-bucket/analytics/"


@given(
    parsers.parse(
        'a SUCCEEDED SELECT with columns "{first}" and "{second}" and '
        "{count:d} rows"
    )
)
def _select_returned(
    outcome: ArtifactOutcome, first: str, second: str, count: int
) -> None:
    outcome.columns = [(first, "integer"), (second, "varchar")]
    outcome.rows = [[1, "alpha"], [2, "beta"]][:count]
    outcome.record = _build_record(
        outcome,
        query="SELECT id, name FROM analytics.t",
        statement_type="DML",
        substatement_type="SELECT",
    )


@given(
    parsers.parse('a CTAS wrote {count:d} parquet files under "{location}"')
)
def _ctas_wrote(outcome: ArtifactOutcome, count: int, location: str) -> None:
    keys = (f"t1/part-0000{i:02d}-f{i}.parquet" for i in range(count))
    outcome.store.objects = {
        ("ctas-bucket", key): b"parquet-bytes" for key in keys
    }
    outcome.record = _build_record(
        outcome,
        query=(
            'CREATE TABLE "analytics"."t1" WITH (external_location = '
            f"'{location}', format = 'PARQUET') AS SELECT 1 AS a"
        ),
        statement_type="DDL",
        substatement_type="CREATE_TABLE_AS_SELECT",
    )


@given(
    parsers.parse(
        'an INSERT appended "{new_file}" to a table at "{location}" '
        'already holding "{old_file}"'
    )
)
def _insert_appended(
    outcome: ArtifactOutcome, new_file: str, location: str, old_file: str
) -> None:
    outcome.appended_paths = [new_file]
    outcome.store.objects = {
        _object_key(path): b"parquet-bytes" for path in (new_file, old_file)
    }
    outcome.record = _build_record(
        outcome,
        query="INSERT INTO analytics.events SELECT 1",
        statement_type="DML",
        substatement_type="INSERT",
        output_snapshot=OutputSnapshot(
            location=location, before_paths=frozenset({old_file})
        ),
    )


@given(
    parsers.parse(
        'an UNLOAD wrote "{new_file}" into "{location}" '
        'already holding "{old_file}"'
    )
)
def _unload_wrote(
    outcome: ArtifactOutcome, new_file: str, location: str, old_file: str
) -> None:
    outcome.appended_paths = [new_file]
    outcome.store.objects = {
        _object_key(path): b"parquet-bytes" for path in (new_file, old_file)
    }
    outcome.record = _build_record(
        outcome,
        query=(
            "UNLOAD (SELECT * FROM analytics.events) "
            f"TO '{location}' WITH (format = 'PARQUET')"
        ),
        statement_type="DML",
        substatement_type="UNLOAD",
        output_snapshot=OutputSnapshot(
            location=location, before_paths=frozenset({old_file})
        ),
    )


@when("the artifact writer persists the execution")
def _persist(outcome: ArtifactOutcome) -> None:
    outcome.persist()


@then("the CSV carries the quoted header row first")
def _csv_header_first(outcome: ArtifactOutcome) -> None:
    assert outcome.record is not None
    body = outcome.store.bytes_of(
        f"{outcome.result_location}{outcome.record.query_execution_id}.csv"
    )
    names = ",".join(f'"{name}"' for name, _type in outcome.columns)
    assert body.startswith(f"{names}\n".encode())


@then("the sidecar records the columns and row count")
def _sidecar_shape(outcome: ArtifactOutcome) -> None:
    assert outcome.record is not None
    body = outcome.store.bytes_of(
        f"{outcome.result_location}"
        f"{outcome.record.query_execution_id}.csv.metadata"
    )
    assert json.loads(body.decode("utf-8")) == {
        "columns": [
            {"Name": name, "Type": column_type}
            for name, column_type in outcome.columns
        ],
        "rows": len(outcome.rows),
    }


@then("the manifest lists each parquet file on its own line")
def _manifest_lines(outcome: ArtifactOutcome) -> None:
    assert outcome.record is not None
    body = outcome.store.bytes_of(
        f"{outcome.result_location}"
        f"{outcome.record.query_execution_id}-manifest.csv"
    )
    paths = [line for line in body.decode("utf-8").split("\n") if line]
    expected = sorted(
        f"s3://{bucket}/{key}"
        for (bucket, key) in outcome.store.objects
        if bucket == "ctas-bucket"
    )
    assert paths == expected


@then("DataManifestLocation points at the manifest file")
def _manifest_location(outcome: ArtifactOutcome) -> None:
    assert outcome.record is not None
    assert outcome.record.data_manifest_location == (
        f"{outcome.result_location}"
        f"{outcome.record.query_execution_id}-manifest.csv"
    )


@then("the manifest lists the appended file only")
def _manifest_appended_only(outcome: ArtifactOutcome) -> None:
    assert outcome.record is not None
    body = outcome.store.bytes_of(
        f"{outcome.result_location}"
        f"{outcome.record.query_execution_id}-manifest.csv"
    )
    paths = [line for line in body.decode("utf-8").split("\n") if line]
    assert paths == sorted(outcome.appended_paths)


def _object_key(s3_uri: str) -> tuple[str, str]:
    assert s3_uri.startswith("s3://"), f"not an s3 URI: {s3_uri}"
    bucket, _, key = s3_uri[len("s3://") :].partition("/")
    return bucket, key


def _build_record(
    outcome: ArtifactOutcome,
    *,
    query: str,
    statement_type: str,
    substatement_type: str,
    output_snapshot: OutputSnapshot | None = None,
) -> QueryExecutionRecord:
    record = ExecutionStore().create(
        query=query,
        workgroup="primary",
        result_configuration=ResultConfiguration(
            output_location=outcome.result_location
        ),
        statement_type=statement_type,
        substatement_type=substatement_type,
        output_snapshot=output_snapshot,
    )
    record.cache_result_page(outcome.columns, outcome.rows)
    return record
