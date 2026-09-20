"""Thin boto3-backed Glue client proxying catalog reads (ADR-0005).

The Athena catalog-introspection operations (ListDatabases, GetDatabase,
ListTableMetadata, GetTableMetadata) read the same moto Glue store that Trino's
hive catalog uses as its metastore, so API answers and engine views cannot
diverge. This module is the only boundary touching Glue (architecture §8.5):
handlers never see boto3 error taxonomy or Glue's storage descriptors — they
receive Athena-wire-shaped records or project-owned Athena exceptions.

Field mapping follows the moto FakeDatabase/FakeTable dict shapes
(``research_repos/moto/moto/glue/models.py:1846,1903``): Athena ``Columns``
come from ``StorageDescriptor.Columns``, the Glue ``CreateTime`` datetime
becomes the Athena ``Timestamp`` epoch number, and Glue
``EntityNotFoundException`` becomes ``MetadataException`` (HTTP 400 per the
AWS API reference for the custom-metastore error).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast

from botocore.exceptions import BotoCoreError, ClientError
from botocore.session import Session

from athena_local.errors import (
    InternalServerException,
    MetadataException,
)

GLUE_ENTITY_NOT_FOUND_CODE = "EntityNotFoundException"
GLUE_REGION = "us-east-1"
GLUE_ACCESS_KEY_ID = "test"
GLUE_SECRET_ACCESS_KEY = "test"


class CatalogClient(Protocol):
    """The four Glue reads this boundary uses (thin interface).

    Parameter names mirror the botocore Glue client keyword arguments, hence
    the PascalCase (ruff N803 ignores below).
    """

    def get_databases(self) -> dict[str, object]: ...
    def get_database(self, Name: str) -> dict[str, object]: ...  # noqa: N803
    def get_tables(  # noqa: N803
        self,
        DatabaseName: str,  # noqa: N803
        Expression: str | None = None,  # noqa: N803
    ) -> dict[str, object]: ...
    def get_table(  # noqa: N803
        self,
        DatabaseName: str,  # noqa: N803
        Name: str,  # noqa: N803
    ) -> dict[str, object]: ...


@dataclass(frozen=True)
class GlueColumn:
    """A column in the Athena ``Column`` wire shape."""

    name: str
    column_type: str
    comment: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "Name": self.name,
            "Type": self.column_type,
        }
        if self.comment is not None:
            payload["Comment"] = self.comment
        return payload


@dataclass(frozen=True)
class GlueDatabase:
    """A Glue database in the Athena ``Database`` wire shape."""

    name: str
    description: str | None = None
    parameters: dict[str, str] | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"Name": self.name}
        if self.description is not None:
            payload["Description"] = self.description
        if self.parameters:
            payload["Parameters"] = dict(self.parameters)
        return payload


@dataclass(frozen=True)
class GlueTableMetadata:
    """A Glue table translated to the Athena ``TableMetadata`` wire shape."""

    name: str
    create_time: float | None = None
    last_access_time: float | None = None
    table_type: str | None = None
    columns: list[GlueColumn] | None = None
    partition_keys: list[GlueColumn] | None = None
    parameters: dict[str, str] | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"Name": self.name}
        if self.create_time is not None:
            payload["CreateTime"] = self.create_time
        # A never-accessed table reports LastAccessTime 0.0 (the shape shown in
        # the CLI get-table-metadata.rst example).
        if self.last_access_time is not None:
            payload["LastAccessTime"] = self.last_access_time
        else:
            payload["LastAccessTime"] = 0.0
        if self.table_type is not None:
            payload["TableType"] = self.table_type
        if self.columns is not None:
            payload["Columns"] = [
                column.to_payload() for column in self.columns
            ]
        if self.partition_keys is not None:
            payload["PartitionKeys"] = [
                column.to_payload() for column in self.partition_keys
            ]
        if self.parameters:
            payload["Parameters"] = dict(self.parameters)
        return payload


class GlueProxy:
    """Reads Athena catalog metadata from moto Glue via a botocore client.

    Third-party error taxonomy is absorbed here: Glue ``EntityNotFoundException``
    surfaces as Athena ``MetadataException`` and transport failures as
    ``InternalServerException``, so handlers only raise project-owned errors.
    """

    def __init__(self, client: CatalogClient) -> None:
        self._client = client

    @classmethod
    def for_endpoint(cls, endpoint_url: str) -> GlueProxy:
        """Build a proxy against ``endpoint_url`` with the moto static keys."""
        session = Session()
        client = session.create_client(
            "glue",
            endpoint_url=endpoint_url,
            region_name=GLUE_REGION,
            aws_access_key_id=GLUE_ACCESS_KEY_ID,
            aws_secret_access_key=GLUE_SECRET_ACCESS_KEY,
        )
        return cls(cast(CatalogClient, client))

    def list_databases(self) -> list[GlueDatabase]:
        response = self._run(
            "GetDatabases", lambda: self._client.get_databases()
        )
        return [
            _database_from_glue(item)
            for item in _objects(response, "DatabaseList")
        ]

    def get_database(self, name: str) -> GlueDatabase:
        response = self._run(
            "GetDatabase",
            lambda: self._client.get_database(Name=name),
            resource=f"database {name}",
        )
        return _database_from_glue(_object(response, "Database"))

    def list_tables(
        self, database_name: str, expression: str | None
    ) -> list[GlueTableMetadata]:
        if expression is None:
            response = self._run(
                "GetTables",
                lambda: self._client.get_tables(DatabaseName=database_name),
                resource=f"database {database_name}",
            )
        else:
            response = self._run(
                "GetTables",
                lambda: self._client.get_tables(
                    DatabaseName=database_name, Expression=expression
                ),
                resource=f"database {database_name}",
            )
        return [
            _table_metadata_from_glue(item)
            for item in _objects(response, "TableList")
        ]

    def get_table(
        self, database_name: str, table_name: str
    ) -> GlueTableMetadata:
        response = self._run(
            "GetTable",
            lambda: self._client.get_table(
                DatabaseName=database_name, Name=table_name
            ),
            resource=f"table {database_name}.{table_name}",
        )
        return _table_metadata_from_glue(_object(response, "Table"))

    def _run(
        self,
        operation: str,
        invoke: Callable[[], dict[str, object]],
        resource: str = "Glue store",
    ) -> dict[str, object]:
        try:
            return invoke()
        except ClientError as error:
            code = _error_code(error)
            if code == GLUE_ENTITY_NOT_FOUND_CODE:
                raise MetadataException(
                    f"{resource} does not exist"
                ) from error
            raise InternalServerException(
                f"Glue {operation} failed with error code {code}: {error}"
            ) from error
        except BotoCoreError as error:
            raise InternalServerException(
                f"Glue transport failure during {operation}: {error}"
            ) from error


def _error_code(error: ClientError) -> str:
    raw = error.response.get("Error")
    if not isinstance(raw, dict):
        return ""
    code = raw.get("Code")
    return code if isinstance(code, str) else ""


def _objects(response: dict[str, object], key: str) -> list[dict[str, object]]:
    raw = response.get(key)
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _object(response: dict[str, object], key: str) -> dict[str, object]:
    raw = response.get(key)
    if not isinstance(raw, dict):
        raise InternalServerException(f"Glue response missing {key} member")
    return raw


def _database_from_glue(record: dict[str, object]) -> GlueDatabase:
    return GlueDatabase(
        name=_string(record, "Name") or "",
        description=_string(record, "Description"),
        parameters=_string_map(record, "Parameters"),
    )


def _table_metadata_from_glue(record: dict[str, object]) -> GlueTableMetadata:
    storage = record.get("StorageDescriptor")
    columns = (
        _columns(storage, "Columns") if isinstance(storage, dict) else None
    )
    return GlueTableMetadata(
        name=_string(record, "Name") or "",
        create_time=_epoch(record, "CreateTime"),
        last_access_time=_epoch(record, "LastAccessTime"),
        table_type=_string(record, "TableType"),
        columns=columns,
        partition_keys=_columns(record, "PartitionKeys"),
        parameters=_string_map(record, "Parameters"),
    )


def _string(record: dict[str, object], key: str) -> str | None:
    raw = record.get(key)
    return raw if isinstance(raw, str) else None


def _string_map(record: dict[str, object], key: str) -> dict[str, str] | None:
    raw = record.get(key)
    if not isinstance(raw, dict):
        return None
    result: dict[str, str] = {}
    for item_key, item_value in raw.items():
        if isinstance(item_key, str) and isinstance(item_value, str):
            result[item_key] = item_value
    return result


def _epoch(record: dict[str, object], key: str) -> float | None:
    raw = record.get(key)
    if isinstance(raw, datetime):
        return raw.timestamp()
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _columns(record: dict[str, object], key: str) -> list[GlueColumn] | None:
    raw = record.get(key)
    if not isinstance(raw, list):
        return None
    return [
        GlueColumn(
            name=_string(column, "Name") or "",
            column_type=_string(column, "Type") or "",
            comment=_string(column, "Comment"),
        )
        for column in raw
        if isinstance(column, dict)
    ]
