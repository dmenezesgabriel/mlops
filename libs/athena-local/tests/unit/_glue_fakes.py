"""Shared named fakes for Glue-backed catalog tests (MD-7).

``FakeGlueClient`` mirrors the moto Glue backend surface the read proxy touches
(moto ``research_repos/moto/moto/glue/models.py:346-417``): get_database /
get_databases / get_table / get_tables with regex ``Expression`` filtering on
table names and ``EntityNotFoundException`` for missing entities. Unit, BDD,
and handler tests construct a real ``GlueProxy`` over this fake, so the
boundary code under test is exactly what ships.
"""

from __future__ import annotations

import re

from botocore.exceptions import ClientError

ENTITY_NOT_FOUND_CODE = "EntityNotFoundException"


def client_error(code: str, message: str) -> ClientError:
    """A shaped botocore ClientError, as the boto3 Glue client raises."""
    return ClientError(
        error_response={
            "Error": {"Code": code, "Message": message},
            "ResponseMetadata": {"HTTPStatusCode": 400},
        },
        operation_name="Probe",
    )


class FakeGlueClient:
    """In-memory double for the boto3 Glue client (F.I.R.S.T., no moto)."""

    def __init__(
        self,
        databases: list[dict[str, object]] | None = None,
        tables: dict[str, list[dict[str, object]]] | None = None,
    ) -> None:
        self.databases = databases if databases is not None else []
        self.tables = tables if tables is not None else {}
        self.list_tables_calls: list[dict[str, object]] = []

    def get_databases(self) -> dict[str, object]:
        return {"DatabaseList": list(self.databases)}

    def get_database(self, Name: str) -> dict[str, object]:  # noqa: N803
        for database in self.databases:
            if database.get("Name") == Name:
                return {"Database": database}
        raise client_error(ENTITY_NOT_FOUND_CODE, f"Database {Name} not found")

    def get_tables(  # noqa: N803
        self,
        DatabaseName: str,  # noqa: N803
        Expression: str | None = None,  # noqa: N803
    ) -> dict[str, object]:
        self.list_tables_calls.append(
            {"DatabaseName": DatabaseName, "Expression": Expression}
        )
        if DatabaseName not in self.tables:
            raise client_error(
                ENTITY_NOT_FOUND_CODE, f"Database {DatabaseName} not found"
            )
        tables = self.tables[DatabaseName]
        if Expression is not None:
            tables = [
                table
                for table in tables
                if isinstance(table.get("Name"), str)
                and re.match(Expression, table["Name"]) is not None
            ]
        return {"TableList": list(tables)}

    def get_table(self, DatabaseName: str, Name: str) -> dict[str, object]:  # noqa: N803
        for table in self.tables.get(DatabaseName, []):
            if table.get("Name") == Name:
                return {"Table": table}
        raise client_error(
            ENTITY_NOT_FOUND_CODE, f"Table {DatabaseName}.{Name} not found"
        )
