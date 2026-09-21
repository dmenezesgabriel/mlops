"""Unit tests for the Glue read proxy (MD-7, ADR-0005).

The proxy is the only code that touches the Glue client, so these tests pin the
Glue→Athena translation (against the moto ``glue/models.py`` FakeDatabase /
FakeTable dict shapes), the ``EntityNotFoundException`` → ``MetadataException``
mapping (MetadataException is Athena's "custom metastore" error, HTTP 400 per
the AWS API reference), and the transport-failure → ``InternalServerException``
path — all against a named fake client, no moto, no docker (F.I.R.S.T.).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from athena_local import glue_proxy as glue_proxy_module
from athena_local.errors import (
    InternalServerException,
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


class AccessDeniedClient(FakeGlueClient):
    """Fake that answers a non-entity Glue ClientError."""

    def get_database(self, Name: str) -> dict[str, object]:  # noqa: N803
        raise client_error("AccessDeniedException", f"Denied for {Name}")


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


def test_list_tables_missing_database_propagates_metadata_exception() -> None:
    proxy = GlueProxy(FakeGlueClient())

    with pytest.raises(MetadataException):
        proxy.list_tables("missing", None)


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
