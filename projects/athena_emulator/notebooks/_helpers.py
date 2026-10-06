"""Probe and cleanup helpers shared by the Athena parity notebooks.

Imported like ``_evidence`` — the kernels run with ``notebooks/`` as cwd.
Every function takes the boto3 client and run-scoped names it needs as
explicit parameters so no helper depends on notebook-kernel globals.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from botocore.client import BaseClient
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


def probe_outcome(call: Callable[[], T]) -> T | Exception:
    """``call()``'s value, or the exception it raised — both are evidence."""
    try:
        return call()
    except Exception as exc:  # a measured probe records any failure
        return exc


def error_detail(error: Exception) -> str:
    """One matrix line: wire Code+status for ClientError, else type+text."""
    if isinstance(error, ClientError):
        code = error.response["Error"]["Code"]
        status = error.response["ResponseMetadata"]["HTTPStatusCode"]
        message = error.response["Error"].get("Message", "")
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
    """(Error.Code, HTTPStatusCode) of a captured ClientError."""
    return (
        error.response["Error"]["Code"],
        error.response["ResponseMetadata"]["HTTPStatusCode"],
    )


def client_error_status(call: Callable[[], object]) -> tuple[str, int] | None:
    """(Error.Code, HTTPStatusCode) when ``call`` fails, else None."""
    error = client_error_of(call)
    if error is None:
        return None
    return error_code_status(error)


def query_execution(athena: BaseClient, query_id: str) -> dict[str, object]:
    """The GetQueryExecution ``QueryExecution`` member for ``query_id``."""
    return athena.get_query_execution(QueryExecutionId=query_id)[
        "QueryExecution"
    ]


def object_keys_under(s3: BaseClient, bucket: str, prefix: str) -> list[str]:
    """Object keys under ``prefix`` in the throwaway bucket."""
    contents = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get(
        "Contents", []
    )
    return [obj["Key"] for obj in contents]


def run_workgroup_names(athena: BaseClient, prefix: str) -> list[str]:
    """Workgroup names carrying this run's (or a failed run's) prefix."""
    return [
        summary["Name"]
        for summary in athena.list_work_groups()["WorkGroups"]
        if summary["Name"].startswith(prefix)
    ]


def delete_workgroup_contents(athena: BaseClient, workgroup_name: str) -> None:
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
    s3: BaseClient,
    prefix: str,
    *,
    extra: Callable[[str], bool] | None = None,
) -> None:
    """Empty and delete every bucket carrying ``prefix``.

    ``extra`` names an additional deletion predicate — nb04 passes the
    wrangler ``aws-athena-query-results-*`` bucket when this run created it.
    """
    for bucket_info in s3.list_buckets()["Buckets"]:
        name = bucket_info["Name"]
        if not (
            name.startswith(prefix) or (extra is not None and extra(name))
        ):
            continue
        objects = s3.list_objects_v2(Bucket=name).get("Contents", [])
        if objects:
            s3.delete_objects(
                Bucket=name,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )
        s3.delete_bucket(Bucket=name)


def delete_run_databases(glue: BaseClient, prefix: str) -> None:
    """Delete tables, then every Glue database carrying ``prefix``."""
    for database_info in glue.get_databases()["DatabaseList"]:
        database_name = database_info["Name"]
        if not database_name.startswith(prefix):
            continue
        tables = glue.get_tables(DatabaseName=database_name)["TableList"]
        for table in tables:
            glue.delete_table(DatabaseName=database_name, Name=table["Name"])
        glue.delete_database(Name=database_name)
