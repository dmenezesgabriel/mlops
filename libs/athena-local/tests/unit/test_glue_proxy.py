"""Unit tests for the Glue read proxy (ADR-0005).

The proxy is the only code that touches the Glue client, so these tests pin the
Glue→Athena translation (against the moto ``glue/models.py`` FakeDatabase /
FakeTable dict shapes), the ``EntityNotFoundException`` → ``MetadataException``
mapping (MetadataException is Athena's "custom metastore" error, HTTP 400 per
the AWS API reference), and the transport-failure → ``InternalServerException``
path — all against a named fake client, no moto, no docker (F.I.R.S.T.).
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from athena_local import glue_proxy as glue_proxy_module
from athena_local.errors import (
    InternalServerException,
    InvalidRequestException,
    MetadataException,
)
from athena_local.glue_proxy import GlueColumn, GlueProxy
from botocore.exceptions import EndpointConnectionError
from tests.unit._glue_fakes import FakeGlueClient, client_error

SAMPLE_DATABASE: dict[str, object] = {
    "Name": "sampledb",
    "Description": "Sample database",
    "Parameters": {"CreatedBy": "Athena", "EXTERNAL": "TRUE"},
}

SAMPLE_TABLE: dict[str, object] = {
    "Name": "counties",
    "TableType": "EXTERNAL_TABLE",
    "CreateTime": datetime(2020, 7, 1, tzinfo=UTC),
    "LastAccessTime": datetime(2020, 7, 2, tzinfo=UTC),
    "StorageDescriptor": {
        "Columns": [
            {"Name": "name", "Type": "string", "Comment": "from deserializer"},
            {"Name": "population", "Type": "int"},
        ]
    },
    "PartitionKeys": [{"Name": "region", "Type": "string"}],
    "Parameters": {"EXTERNAL": "TRUE", "location": "s3://bucket/json"},
}


class BrokenTransportClient(FakeGlueClient):
    """Fake whose reads fail at the boto3 transport layer."""

    def get_databases(self) -> dict[str, object]:
        raise EndpointConnectionError(endpoint_url="http://moto:5000")


class BrokenDeleteClient(FakeGlueClient):
    """Fake whose DeleteTable fails at the boto3 transport layer."""

    def delete_table(self, DatabaseName: str, Name: str) -> None:  # noqa: N803
        raise EndpointConnectionError(endpoint_url="http://moto:5000")


class AccessDeniedClient(FakeGlueClient):
    """Fake that answers a non-entity Glue ClientError."""

    def get_database(self, Name: str) -> dict[str, object]:  # noqa: N803
        raise client_error("AccessDeniedException", f"Denied for {Name}")


class BadPatternClient(FakeGlueClient):
    """Fake dying with a non-boto error, like moto's in-process ``re.error``."""

    def get_databases(self) -> dict[str, object]:
        raise re.error("bad pattern")


class MalformedDatabaseClient(FakeGlueClient):
    """Fake whose GetDatabase answer lacks a JSON object member."""

    def get_database(self, Name: str) -> dict[str, object]:  # noqa: N803
        return {"Database": "not-an-object"}


def test_list_databases_translates_glue_database() -> None:
    proxy = GlueProxy(FakeGlueClient(databases=[SAMPLE_DATABASE]))

    databases = proxy.list_databases()

    assert len(databases) == 1
    assert databases[0].name == "sampledb"
    assert databases[0].description == "Sample database"
    assert databases[0].parameters == {
        "CreatedBy": "Athena",
        "EXTERNAL": "TRUE",
    }


def test_list_databases_returns_empty_for_empty_store() -> None:
    proxy = GlueProxy(FakeGlueClient())

    assert proxy.list_databases() == []


def test_get_database_returns_record() -> None:
    proxy = GlueProxy(FakeGlueClient(databases=[SAMPLE_DATABASE]))

    database = proxy.get_database("sampledb")

    assert database.name == "sampledb"
    assert database.description == "Sample database"


def test_database_parameters_drop_the_engine_query_stamp() -> None:
    # Trino's Glue metastore stamps ``trino_query_id`` on every database it
    # creates; real AWS surfaces only caller DBPROPERTIES, and consumers that
    # round-trip Parameters (the terraform provider's ``properties`` attribute
    # is ForceNew) treat the stamp as drift.
    stamped = {
        "Name": "enginedb",
        "Parameters": {
            "trino_query_id": "20260927_000000_00001_abc",
            "team": "data",
        },
    }
    proxy = GlueProxy(FakeGlueClient(databases=[stamped]))

    assert proxy.get_database("enginedb").parameters == {"team": "data"}
    assert proxy.list_databases()[0].parameters == {"team": "data"}


def test_database_parameters_none_when_only_engine_stamp() -> None:
    stamped = {
        "Name": "enginedb",
        "Parameters": {"trino_query_id": "20260927_000000_00001_abc"},
    }
    proxy = GlueProxy(FakeGlueClient(databases=[stamped]))

    assert proxy.get_database("enginedb").parameters is None


def test_get_database_malformed_member_is_internal_server() -> None:
    """A member that is not a JSON object breaks the wire contract — a
    shaped 500, never a silent None parse."""
    proxy = GlueProxy(MalformedDatabaseClient())

    with pytest.raises(
        InternalServerException, match="missing Database member"
    ):
        proxy.get_database("sampledb")


def test_get_database_missing_raises_metadata_exception() -> None:
    proxy = GlueProxy(FakeGlueClient())

    with pytest.raises(MetadataException) as exc_info:
        proxy.get_database("missing")

    assert "missing" in exc_info.value.message


def test_get_database_non_entity_error_is_internal_server() -> None:
    proxy = GlueProxy(AccessDeniedClient())

    with pytest.raises(InternalServerException):
        proxy.get_database("restricted")


def test_transport_failure_is_internal_server_exception() -> None:
    proxy = GlueProxy(BrokenTransportClient())

    with pytest.raises(InternalServerException):
        proxy.list_databases()


def test_list_tables_passes_expression_through() -> None:
    fake = FakeGlueClient(tables={"geo": [SAMPLE_TABLE]})
    proxy = GlueProxy(fake)

    proxy.list_tables("geo", "count.*")

    assert fake.list_tables_calls == [
        {"DatabaseName": "geo", "Expression": "count.*"}
    ]


def test_list_tables_without_expression_omits_key() -> None:
    fake = FakeGlueClient(tables={"geo": [SAMPLE_TABLE]})
    proxy = GlueProxy(fake)

    proxy.list_tables("geo", None)

    assert fake.list_tables_calls == [
        {"DatabaseName": "geo", "Expression": None}
    ]


def test_list_tables_translates_storage_descriptor_columns() -> None:
    proxy = GlueProxy(FakeGlueClient(tables={"geo": [SAMPLE_TABLE]}))

    tables = proxy.list_tables("geo", None)

    assert len(tables) == 1
    table = tables[0]
    assert table.name == "counties"
    assert table.table_type == "EXTERNAL_TABLE"
    assert table.create_time == 1593561600.0
    assert table.last_access_time == 1593648000.0
    assert table.columns == [
        GlueColumn(
            name="name",
            column_type="string",
            comment="from deserializer",
        ),
        GlueColumn(name="population", column_type="int", comment=None),
    ]
    assert table.partition_keys == [
        GlueColumn(name="region", column_type="string", comment=None)
    ]
    assert table.parameters == {
        "EXTERNAL": "TRUE",
        "location": "s3://bucket/json",
    }


def test_list_tables_numeric_create_time_passes_through_as_epoch() -> None:
    """A numeric CreateTime (not a datetime) is already an epoch value."""
    table = {**SAMPLE_TABLE, "CreateTime": 1_700_000_000}
    proxy = GlueProxy(FakeGlueClient(tables={"geo": [table]}))

    tables = proxy.list_tables("geo", None)

    assert tables[0].create_time == 1_700_000_000.0


def test_list_tables_skips_non_object_column_entries() -> None:
    """A malformed Columns entry is dropped, not surfaced as a blank column."""
    table = {
        **SAMPLE_TABLE,
        "StorageDescriptor": {
            "Columns": ["junk", {"Name": "population", "Type": "int"}]
        },
    }
    proxy = GlueProxy(FakeGlueClient(tables={"geo": [table]}))

    tables = proxy.list_tables("geo", None)

    assert tables[0].columns == [
        GlueColumn(name="population", column_type="int", comment=None)
    ]


def test_list_tables_missing_database_propagates_metadata_exception() -> None:
    proxy = GlueProxy(FakeGlueClient())

    with pytest.raises(MetadataException):
        proxy.list_tables("missing", None)


@pytest.mark.parametrize("expression", ["(", "t["])
def test_list_tables_malformed_expression_is_invalid_request(
    expression: str,
) -> None:
    """A malformed Expression rejects like real Glue's 400, naming it.

    The Glue store filters table names with the Expression pattern; a
    malformed pattern once raised ``re.error`` past ``_run``'s boto-only
    catches and surfaced a 500 where real Glue answers 400.
    """
    fake = FakeGlueClient(tables={"geo": [SAMPLE_TABLE]})
    proxy = GlueProxy(fake)

    with pytest.raises(InvalidRequestException) as exc_info:
        proxy.list_tables("geo", expression)

    assert repr(expression) in exc_info.value.message
    assert fake.list_tables_calls == []


def test_unexpected_client_error_is_shaped_internal_server() -> None:
    """A non-boto escape from the client call is absorbed as a 500.

    Only ``ClientError``/``BotoCoreError`` were shaped; anything else —
    an in-process store's ``re.error``, a botocore internals bug — leaked
    past ``_run`` unshaped.
    """
    proxy = GlueProxy(BadPatternClient())

    with pytest.raises(InternalServerException, match="GetDatabases"):
        proxy.list_databases()


def test_get_table_returns_record() -> None:
    proxy = GlueProxy(FakeGlueClient(tables={"geo": [SAMPLE_TABLE]}))

    table = proxy.get_table("geo", "counties")

    assert table.name == "counties"
    assert table.table_type == "EXTERNAL_TABLE"


def test_get_table_maps_storage_descriptor_location() -> None:
    table = {
        "Name": "events",
        "StorageDescriptor": {
            "Columns": [{"Name": "id", "Type": "int"}],
            "Location": "s3://data-bucket/events/",
        },
    }
    proxy = GlueProxy(FakeGlueClient(tables={"analytics": [table]}))

    metadata = proxy.get_table("analytics", "events")

    assert metadata.location == "s3://data-bucket/events/"


def test_get_table_without_location_reports_none() -> None:
    proxy = GlueProxy(FakeGlueClient(tables={"geo": [SAMPLE_TABLE]}))

    metadata = proxy.get_table("geo", "counties")

    assert metadata.location is None


def test_get_table_missing_raises_metadata_exception() -> None:
    proxy = GlueProxy(FakeGlueClient())

    with pytest.raises(MetadataException) as exc_info:
        proxy.get_table("geo", "missing")

    assert "missing" in exc_info.value.message


def test_delete_table_removes_the_catalog_entry() -> None:
    client = FakeGlueClient(tables={"analytics": [SAMPLE_TABLE]})
    proxy = GlueProxy(client)

    proxy.delete_table("analytics", "counties")

    assert client.delete_table_calls == [("analytics", "counties")]
    assert client.tables["analytics"] == []


def test_delete_table_missing_raises_metadata_exception() -> None:
    proxy = GlueProxy(FakeGlueClient(tables={"analytics": []}))

    with pytest.raises(MetadataException):
        proxy.delete_table("analytics", "gone")


def test_delete_table_transport_failure_is_internal_server() -> None:
    proxy = GlueProxy(BrokenDeleteClient())

    with pytest.raises(InternalServerException):
        proxy.delete_table("analytics", "counties")


def test_records_are_immutable() -> None:
    proxy = GlueProxy(FakeGlueClient(databases=[SAMPLE_DATABASE]))

    with pytest.raises(FrozenInstanceError):
        proxy.list_databases()[0].name = "mutated"  # type: ignore[misc]


def test_for_endpoint_creates_glue_client_with_moto_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    class RecordingSession:
        def create_client(self, service_name: str, **kwargs: object) -> object:
            recorded["service_name"] = service_name
            recorded.update(kwargs)
            return FakeGlueClient()

    monkeypatch.setattr(glue_proxy_module, "Session", RecordingSession)

    proxy = GlueProxy.for_endpoint("http://moto:5000")

    assert recorded["service_name"] == "glue"
    assert recorded["endpoint_url"] == "http://moto:5000"
    assert recorded["region_name"] == "us-east-1"
    assert recorded["aws_access_key_id"] == "test"
    assert recorded["aws_secret_access_key"] == "test"
    assert isinstance(proxy, GlueProxy)
