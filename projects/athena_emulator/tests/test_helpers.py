"""In-process unit tests for ``notebooks/_helpers.py`` — no stack required.

Loads the helpers module by file path (the notebooks directory is not a
package; notebook kernels resolve it via cwd instead). Boto3 clients are
replaced by named recording fakes — no network is touched.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import NoReturn, cast

import pytest
from botocore.exceptions import ClientError

PROJECT_DIR = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "_helpers", PROJECT_DIR / "notebooks" / "_helpers.py"
)
assert _SPEC is not None and _SPEC.loader is not None
helpers = importlib.util.module_from_spec(_SPEC)
sys.modules["_helpers"] = helpers
_SPEC.loader.exec_module(helpers)


def _raise(error: Exception) -> NoReturn:
    raise error


def _client_error(code: str, status: int, message: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "OperationName",
    )


class FakeAthenaClient:
    """Recording stand-in for the athena client calls the helpers make."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.executions: dict[str, dict[str, object]] = {}
        self.work_groups: list[dict[str, object]] = []
        self.named_query_ids: dict[str, list[str]] = {}
        self.prepared_statements: dict[str, list[dict[str, str]]] = {}

    def _record(self, op: str, kwargs: dict[str, object]) -> None:
        self.calls.append((op, kwargs))

    def get_query_execution(self, **kwargs: object) -> dict[str, object]:
        self._record("get_query_execution", kwargs)
        return {
            "QueryExecution": self.executions[
                cast(str, kwargs["QueryExecutionId"])
            ]
        }

    def list_work_groups(self, **kwargs: object) -> dict[str, object]:
        self._record("list_work_groups", kwargs)
        return {"WorkGroups": self.work_groups}

    def list_named_queries(self, **kwargs: object) -> dict[str, object]:
        self._record("list_named_queries", kwargs)
        return {
            "NamedQueryIds": self.named_query_ids[
                cast(str, kwargs["WorkGroup"])
            ]
        }

    def delete_named_query(self, **kwargs: object) -> None:
        self._record("delete_named_query", kwargs)

    def list_prepared_statements(self, **kwargs: object) -> dict[str, object]:
        self._record("list_prepared_statements", kwargs)
        return {
            "PreparedStatements": self.prepared_statements[
                cast(str, kwargs["WorkGroup"])
            ]
        }

    def delete_prepared_statement(self, **kwargs: object) -> None:
        self._record("delete_prepared_statement", kwargs)

    def delete_work_group(self, **kwargs: object) -> None:
        self._record("delete_work_group", kwargs)


class FakeS3Client:
    """Recording stand-in for the s3 client calls the helpers make."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.bucket_names: list[str] = []
        self.list_objects_contents: dict[str, list[dict[str, str]]] = {}

    def _record(self, op: str, kwargs: dict[str, object]) -> None:
        self.calls.append((op, kwargs))

    def list_buckets(self, **kwargs: object) -> dict[str, object]:
        self._record("list_buckets", kwargs)
        return {"Buckets": [{"Name": name} for name in self.bucket_names]}

    def list_objects_v2(self, **kwargs: object) -> dict[str, object]:
        self._record("list_objects_v2", kwargs)
        return {
            "Contents": self.list_objects_contents.get(
                cast(str, kwargs["Bucket"]), []
            )
        }

    def delete_objects(self, **kwargs: object) -> None:
        self._record("delete_objects", kwargs)

    def delete_bucket(self, **kwargs: object) -> None:
        self._record("delete_bucket", kwargs)


class FakeGlueClient:
    """Recording stand-in for the glue client calls the helpers make."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.database_names: list[str] = []
        self.table_names: dict[str, list[str]] = {}

    def _record(self, op: str, kwargs: dict[str, object]) -> None:
        self.calls.append((op, kwargs))

    def get_databases(self, **kwargs: object) -> dict[str, object]:
        self._record("get_databases", kwargs)
        return {
            "DatabaseList": [{"Name": name} for name in self.database_names]
        }

    def get_tables(self, **kwargs: object) -> dict[str, object]:
        self._record("get_tables", kwargs)
        return {
            "TableList": [
                {"Name": name}
                for name in self.table_names[cast(str, kwargs["DatabaseName"])]
            ]
        }

    def delete_table(self, **kwargs: object) -> None:
        self._record("delete_table", kwargs)

    def delete_database(self, **kwargs: object) -> None:
        self._record("delete_database", kwargs)


def test_probe_outcome_returns_value() -> None:
    assert helpers.probe_outcome(lambda: 42) == 42


def test_probe_outcome_returns_the_exception_it_caught() -> None:
    error = RuntimeError("boom")
    assert helpers.probe_outcome(lambda: _raise(error)) is error


def test_error_detail_formats_client_error() -> None:
    error = _client_error("InvalidRequestException", 400, "line one\nline two")
    assert (
        helpers.error_detail(error)
        == "InvalidRequestException (400): line one"
    )


def test_error_detail_formats_generic_error() -> None:
    assert helpers.error_detail(ValueError("bad\nmore")) == "ValueError: bad"


def test_error_detail_handles_empty_message() -> None:
    assert helpers.error_detail(ValueError()) == "ValueError: "


def test_client_error_of_captures_client_error() -> None:
    error = _client_error("X", 418, "m")
    assert helpers.client_error_of(lambda: _raise(error)) is error


def test_client_error_of_returns_none_on_success() -> None:
    assert helpers.client_error_of(lambda: object()) is None


def test_client_error_of_propagates_non_client_errors() -> None:
    with pytest.raises(ValueError, match="not a ClientError"):
        helpers.client_error_of(
            lambda: _raise(ValueError("not a ClientError"))
        )


def test_error_code_status_extracts_code_and_status() -> None:
    error = _client_error("Bogus", 418, "x")
    assert helpers.error_code_status(error) == ("Bogus", 418)


def test_client_error_status_returns_code_status_tuple() -> None:
    error = _client_error("InvalidRequestException", 400, "m")
    assert helpers.client_error_status(lambda: _raise(error)) == (
        "InvalidRequestException",
        400,
    )


def test_client_error_status_returns_none_on_success() -> None:
    assert helpers.client_error_status(lambda: object()) is None


def test_query_execution_returns_the_member() -> None:
    athena = FakeAthenaClient()
    athena.executions["q-1"] = {"Status": {"State": "SUCCEEDED"}}
    assert helpers.query_execution(athena, "q-1") == {
        "Status": {"State": "SUCCEEDED"}
    }
    assert athena.calls == [
        ("get_query_execution", {"QueryExecutionId": "q-1"})
    ]


def test_object_keys_under_lists_keys() -> None:
    s3 = FakeS3Client()
    s3.list_objects_contents["bkt"] = [
        {"Key": "results/a"},
        {"Key": "results/b"},
    ]
    assert helpers.object_keys_under(s3, "bkt", "results/") == [
        "results/a",
        "results/b",
    ]
    assert s3.calls == [
        ("list_objects_v2", {"Bucket": "bkt", "Prefix": "results/"})
    ]


def test_object_keys_under_empty_when_no_contents() -> None:
    s3 = FakeS3Client()
    assert helpers.object_keys_under(s3, "bkt", "none/") == []


def test_run_workgroup_names_filters_by_prefix() -> None:
    athena = FakeAthenaClient()
    athena.work_groups = [
        {"Name": "nb02-a"},
        {"Name": "primary"},
        {"Name": "nb02-b"},
    ]
    assert helpers.run_workgroup_names(athena, "nb02-") == [
        "nb02-a",
        "nb02-b",
    ]


def test_delete_workgroup_contents_removes_queries_then_statements() -> None:
    athena = FakeAthenaClient()
    athena.named_query_ids["wg"] = ["q1", "q2"]
    athena.prepared_statements["wg"] = [{"StatementName": "s1"}]
    helpers.delete_workgroup_contents(athena, "wg")
    assert athena.calls == [
        ("list_named_queries", {"WorkGroup": "wg"}),
        ("delete_named_query", {"NamedQueryId": "q1"}),
        ("delete_named_query", {"NamedQueryId": "q2"}),
        ("list_prepared_statements", {"WorkGroup": "wg"}),
        (
            "delete_prepared_statement",
            {"StatementName": "s1", "WorkGroup": "wg"},
        ),
    ]


def test_delete_run_buckets_empties_and_deletes_only_prefixed() -> None:
    s3 = FakeS3Client()
    s3.bucket_names = ["nb02-a", "other-bucket", "nb02-b"]
    s3.list_objects_contents = {"nb02-a": [{"Key": "x"}], "nb02-b": []}
    helpers.delete_run_buckets(s3, "nb02-")
    assert s3.calls == [
        ("list_buckets", {}),
        ("list_objects_v2", {"Bucket": "nb02-a"}),
        (
            "delete_objects",
            {"Bucket": "nb02-a", "Delete": {"Objects": [{"Key": "x"}]}},
        ),
        ("delete_bucket", {"Bucket": "nb02-a"}),
        ("list_objects_v2", {"Bucket": "nb02-b"}),
        ("delete_bucket", {"Bucket": "nb02-b"}),
    ]


def test_delete_run_buckets_honors_extra_predicate() -> None:
    s3 = FakeS3Client()
    s3.bucket_names = ["aws-athena-query-results-x", "unrelated"]
    helpers.delete_run_buckets(
        s3,
        "nb04-",
        extra=lambda name: name.startswith("aws-athena-query-results-"),
    )
    assert s3.calls == [
        ("list_buckets", {}),
        ("list_objects_v2", {"Bucket": "aws-athena-query-results-x"}),
        ("delete_bucket", {"Bucket": "aws-athena-query-results-x"}),
    ]


def test_delete_run_databases_deletes_tables_then_databases() -> None:
    glue = FakeGlueClient()
    glue.database_names = ["nb04_a", "unrelated", "nb04_b"]
    glue.table_names = {"nb04_a": ["t1", "t2"], "nb04_b": []}
    helpers.delete_run_databases(glue, "nb04_")
    assert glue.calls == [
        ("get_databases", {}),
        ("get_tables", {"DatabaseName": "nb04_a"}),
        ("delete_table", {"DatabaseName": "nb04_a", "Name": "t1"}),
        ("delete_table", {"DatabaseName": "nb04_a", "Name": "t2"}),
        ("delete_database", {"Name": "nb04_a"}),
        ("get_tables", {"DatabaseName": "nb04_b"}),
        ("delete_database", {"Name": "nb04_b"}),
    ]


def _top_level_def_names(notebook_path: Path) -> set[str]:
    notebook = json.loads(notebook_path.read_text())
    names: set[str] = set()
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        try:
            tree = ast.parse("".join(cell["source"]))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.ClassDef):
                names.add(node.name)
    return names


def test_no_notebook_redefines_a_shared_helper() -> None:
    shared = set(helpers.__all__)
    notebooks = sorted(PROJECT_DIR.glob("notebooks/*.ipynb"))
    offenders = {
        path.name: sorted(_top_level_def_names(path) & shared)
        for path in notebooks
        if _top_level_def_names(path) & shared
    }
    assert offenders == {}, f"shared helpers re-defined in {offenders}"
