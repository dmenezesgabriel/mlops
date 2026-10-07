"""Probe and cleanup helpers shared by the Athena parity notebooks.

Imported like ``_evidence`` — the kernels run with ``notebooks/`` as cwd.
Every function takes the boto3 client and run-scoped names it needs as
explicit parameters so no helper depends on notebook-kernel globals.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from botocore.exceptions import ClientError

__all__ = [
    "client_error_of",
    "client_error_status",
    "delete_run_buckets",
    "delete_run_databases",
    "delete_workgroup_contents",
    "error_code_status",
    "error_detail",
    "object_keys_under",
    "probe_outcome",
    "query_execution",
    "run_workgroup_names",
]

T = TypeVar("T")


# boto3 service operations are dynamic — BaseClient carries none of them
# statically — so the consumed surface is declared as protocols. Response
# shapes are Any: the wire returns service-dependent JSON.
class AthenaOps(Protocol):
    def get_query_execution(self, **kwargs: object) -> dict[str, Any]: ...
    def list_work_groups(self, **kwargs: object) -> dict[str, Any]: ...
    def list_named_queries(self, **kwargs: object) -> dict[str, Any]: ...
    def delete_named_query(self, **kwargs: object) -> None: ...
    def list_prepared_statements(self, **kwargs: object) -> dict[str, Any]: ...
    def delete_prepared_statement(self, **kwargs: object) -> None: ...


class S3Ops(Protocol):
    def list_buckets(self, **kwargs: object) -> dict[str, Any]: ...
    def list_objects_v2(self, **kwargs: object) -> dict[str, Any]: ...
    def delete_objects(self, **kwargs: object) -> None: ...
    def delete_bucket(self, **kwargs: object) -> None: ...


class GlueOps(Protocol):
    def get_databases(self, **kwargs: object) -> dict[str, Any]: ...
    def get_tables(self, **kwargs: object) -> dict[str, Any]: ...
    def delete_table(self, **kwargs: object) -> None: ...
    def delete_database(self, **kwargs: object) -> None: ...


def probe_outcome(call: Callable[[], T]) -> T | Exception:
    """``call()``'s value, or the exception it raised — both are evidence."""
    try:
        return call()
    except Exception as exc:  # a measured probe records any failure
        return exc


def error_detail(error: Exception) -> str:
    """One matrix line: wire Code+status for ClientError, else type+text."""
    if isinstance(error, ClientError):
        code, status = error_code_status(error)
        error_info = error.response.get("Error") or {}
        message = error_info.get("Message") or ""
        return f"{code} ({status}): {message.splitlines()[0][:80]}"
    first = str(error).splitlines()[0] if str(error) else ""
    return f"{type(error).__name__}: {first[:80]}"


def client_error_of(call: Callable[[], object]) -> ClientError | None:
    """The ClientError ``call`` raised, or None when it succeeded."""
    try:
        call()
    except ClientError as exc:
        return exc
    return None


def error_code_status(error: ClientError) -> tuple[str, int]:
    """(Error.Code, HTTPStatusCode) of a captured ClientError.

    The response keys are typed non-required — a malformed wire payload
    degrades to placeholders instead of KeyError inside a probe.
    """
    error_info = error.response.get("Error") or {}
    metadata = error.response.get("ResponseMetadata") or {}
    return (
        error_info.get("Code") or "UnknownError",
        metadata.get("HTTPStatusCode") or 0,
    )


def client_error_status(call: Callable[[], object]) -> tuple[str, int] | None:
    """(Error.Code, HTTPStatusCode) when ``call`` fails, else None."""
    error = client_error_of(call)
    if error is None:
        return None
    return error_code_status(error)


def query_execution(athena: AthenaOps, query_id: str) -> dict[str, object]:
    """The GetQueryExecution ``QueryExecution`` member for ``query_id``."""
    return athena.get_query_execution(QueryExecutionId=query_id)[
        "QueryExecution"
    ]


def object_keys_under(s3: S3Ops, bucket: str, prefix: str) -> list[str]:
    """Object keys under ``prefix`` in the throwaway bucket."""
    contents = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get(
        "Contents", []
    )
    return [obj["Key"] for obj in contents]


def run_workgroup_names(athena: AthenaOps, prefix: str) -> list[str]:
    """Workgroup names carrying this run's (or a failed run's) prefix."""
    return [
        summary["Name"]
        for summary in athena.list_work_groups()["WorkGroups"]
        if summary["Name"].startswith(prefix)
    ]


def delete_workgroup_contents(athena: AthenaOps, workgroup_name: str) -> None:
    """Delete the named queries and prepared statements in a workgroup."""
    queries = athena.list_named_queries(WorkGroup=workgroup_name)
    for query_id in queries.get("NamedQueryIds", []):
        athena.delete_named_query(NamedQueryId=query_id)
    statements = athena.list_prepared_statements(WorkGroup=workgroup_name)
    for summary in statements.get("PreparedStatements", []):
        athena.delete_prepared_statement(
            StatementName=summary["StatementName"], WorkGroup=workgroup_name
        )


def delete_run_buckets(
    s3: S3Ops,
    prefix: str,
    *,
    extra: Callable[[str], bool] | None = None,
) -> None:
    """Empty and delete every bucket carrying ``prefix``.

    ``extra`` names an additional deletion predicate — nb04 passes the
    wrangler ``aws-athena-query-results-*`` bucket when this run created it.
    """
    also_delete: Callable[[str], bool] = extra or (lambda _name: False)
    for bucket_info in s3.list_buckets()["Buckets"]:
        name = bucket_info["Name"]
        if not (name.startswith(prefix) or also_delete(name)):
            continue
        objects = s3.list_objects_v2(Bucket=name).get("Contents", [])
        if objects:
            s3.delete_objects(
                Bucket=name,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )
        s3.delete_bucket(Bucket=name)


def delete_run_databases(glue: GlueOps, prefix: str) -> None:
    """Delete tables, then every Glue database carrying ``prefix``."""
    for database_info in glue.get_databases()["DatabaseList"]:
        database_name = database_info["Name"]
        if not database_name.startswith(prefix):
            continue
        tables = glue.get_tables(DatabaseName=database_name)["TableList"]
        for table in tables:
            glue.delete_table(DatabaseName=database_name, Name=table["Name"])
        glue.delete_database(Name=database_name)
