"""Query result artifact writers per ADR-0007/0010 (AR-1).

The emulator owns artifact bytes — nothing is left to Trino's writer
(ADR-0006). ``ArtifactWriter`` implements the executor's
``ResultArtifactWriter`` protocol and persists, before SUCCEEDED (ADR-0009
#4): ``{QueryID}.csv`` with the quoted header row as line 1 (wrangler reads
it by dtype name without ``names=`` — awswrangler/athena/_read.py:225-238),
headerless tab ``{QueryID}.txt`` (names are passed explicitly at _utils.py
:200-213), and a ``{QueryID}-manifest.csv`` of one ``s3://`` file per line
plus a ``{QueryID}.metadata`` sidecar for CTAS/INSERT/UNLOAD
(_read.py:62-81). Rows come from the record the executor cached, never from
the page, so this module sees trino types only in the protocol-mandated
parameter.

The ``external_location`` of a CTAS is read from the (comment-stripped) SQL
because the emulator's Trino writes the parquet files there and GetQueryResults
does not know the output paths; the manifest lists exactly those files.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from typing import Literal

from athena_local.executions import QueryExecutionRecord
from athena_local.executor import ArtifactWriteError
from athena_local.s3_writer import S3Writer, S3WriterError
from athena_local.statement_classification import DDL, UTILITY, _strip_comments
from athena_local.trino_client import TrinoPage

MANIFEST_SUBSTATEMENTS = frozenset(
    {"CREATE_TABLE_AS_SELECT", "INSERT", "UNLOAD"}
)

# ``''`` is SQL's escaped quote; the kept text still holds the literal the
# same way _strip_comments preserves string literals.
_EXTERNAL_LOCATION_RE = re.compile(
    r"external_location\s*=\s*'((?:[^']|'')*)'",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class ArtifactPlan:
    """File naming and shape for one statement outcome (ADR-0007 #1)."""

    kind: Literal["csv", "txt", "manifest"]
    data_suffix: str
    metadata_suffix: str

    def data_name(self, query_id: str) -> str:
        return f"{query_id}{self.data_suffix}"

    def metadata_name(self, query_id: str) -> str:
        return f"{query_id}{self.metadata_suffix}"


def artifact_plan(
    statement_type: str | None, substatement_type: str | None
) -> ArtifactPlan:
    """Pick the artifact shape for a statement's wire classification.

    CTAS / INSERT / UNLOAD write a ``-manifest.csv`` listing the created S3
    files (wrangler reads ``Statistics.DataManifestLocation`` at
    _read.py:62-81); DDL (non-CTAS) and UTILITY results are the headerless
    ``.txt`` (wrangler _utils.py:200-213); everything else is the ``.csv``
    whose quoted header row is line 1 (ADR-0010).
    """
    if substatement_type in MANIFEST_SUBSTATEMENTS:
        return ArtifactPlan("manifest", "-manifest.csv", ".metadata")
    if statement_type in (DDL, UTILITY):
        return ArtifactPlan("txt", ".txt", ".txt.metadata")
    return ArtifactPlan("csv", ".csv", ".csv.metadata")


class ArtifactWriter:
    """Persists an execution's result artifacts before SUCCEEDED (ADR-0007).

    The ``TrinoPage`` parameter satisfies the executor's protocol; rows are
    always read from the record the executor cached (ADR-0009 #4).
    """

    def __init__(self, s3: S3Writer) -> None:
        self._s3 = s3

    async def write(
        self, execution: QueryExecutionRecord, _final_page: TrinoPage
    ) -> None:
        # The page is ignored on purpose: artifact bytes come from the record's
        # cached columns/rows, which the executor stashed before calling us.
        plan = artifact_plan(
            execution.statement_type, execution.substatement_type
        )
        try:
            if plan.kind == "manifest":
                self._write_manifest(execution, plan)
            else:
                self._write_rows(execution, plan)
        except S3WriterError as error:
            raise ArtifactWriteError(str(error)) from error

    def _write_rows(
        self, execution: QueryExecutionRecord, plan: ArtifactPlan
    ) -> None:
        location = _output_prefix(execution)
        self._s3.put_object(
            location + plan.data_name(execution.query_execution_id),
            _rows_bytes(plan, execution.result_columns, execution.result_rows),
        )
        self._s3.put_object(
            location + plan.metadata_name(execution.query_execution_id),
            _metadata_bytes(execution.result_columns, execution.result_rows),
        )

    def _write_manifest(
        self, execution: QueryExecutionRecord, plan: ArtifactPlan
    ) -> None:
        target = _external_location(execution.query)
        if target is None:
            raise ArtifactWriteError(
                f"Execution {execution.query_execution_id} has no "
                "external_location property to enumerate; cannot write a "
                "data manifest"
            )
        location = _output_prefix(execution)
        paths = sorted(self._s3.list_object_paths(target))
        manifest_path = location + plan.data_name(execution.query_execution_id)
        self._s3.put_object(manifest_path, _manifest_bytes(paths))
        execution.data_manifest_location = manifest_path
        self._s3.put_object(
            location + plan.metadata_name(execution.query_execution_id),
            _metadata_bytes(execution.result_columns, execution.result_rows),
        )


def _output_prefix(execution: QueryExecutionRecord) -> str:
    result_configuration = execution.result_configuration
    output_location = (
        result_configuration.output_location
        if result_configuration is not None
        else None
    )
    if not output_location:
        raise ArtifactWriteError(
            f"Execution {execution.query_execution_id} has no "
            "ResultConfiguration.OutputLocation to write artifacts into"
        )
    return output_location.rstrip("/") + "/"


def _rows_bytes(
    plan: ArtifactPlan,
    columns: list[tuple[str, str]],
    rows: list[list[object]],
) -> bytes:
    delimiter = "," if plan.kind == "csv" else "\t"
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=delimiter,
        quoting=csv.QUOTE_ALL,
        lineterminator="\n",
    )
    if plan.kind == "csv":
        writer.writerow([name for name, _type in columns])
    for row in rows:
        writer.writerow(["" if value is None else str(value) for value in row])
    return buffer.getvalue().encode("utf-8")


def _metadata_bytes(
    columns: list[tuple[str, str]], rows: list[list[object]]
) -> bytes:
    document: dict[str, object] = {
        "columns": [
            {"Name": name, "Type": column_type}
            for name, column_type in columns
        ],
        "rows": len(rows),
    }
    return json.dumps(document).encode("utf-8")


def _manifest_bytes(paths: list[str]) -> bytes:
    return "".join(f"{path}\n" for path in paths).encode("utf-8")


def _external_location(query: str) -> str | None:
    with_properties = _strip_comments(query)
    match = _EXTERNAL_LOCATION_RE.search(with_properties)
    if match is None:
        return None
    return match.group(1).replace("''", "'")
