"""Consumer-parity integration: catalog reads against a live moto Glue.

MD-7 acceptance. A live moto server backs the Glue store; the app's catalog
metadata handlers are re-bound to a ``GlueProxy`` pointed at it, and a real
botocore athena client round-trips ListDatabases / GetDatabase /
ListTableMetadata / GetTableMetadata over the JSON-1.1 wire protocol. The same
moto instance serves both the seeding boto3 Glue writes and the proxy reads,
pinning ADR-0005's single-store guarantee at the HTTP boundary.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

import boto3
import pytest
from athena_local.catalog_metadata import register_catalog_metadata_handlers
from athena_local.glue_proxy import GlueProxy
from athena_local.main import data_catalog_store
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from moto.backends import get_backend
from tests.integration.conftest import LiveAthenaServer, LiveMotoServer

CLI_SAMPLE_DATABASE: dict[str, str | dict[str, str]] = {
    "Name": "sampledb",
    "Description": "Sample database",
    "Parameters": {"CreatedBy": "Athena", "EXTERNAL": "TRUE"},
}


@dataclass
class CatalogMetadataStack:
    """The live stack: athena wire client plus the seeding glue client."""

    glue: BaseClient
    athena: BaseClient


@pytest.fixture()
def catalog_metadata_stack(
    live_moto_server: LiveMotoServer,
    live_athena_server: LiveAthenaServer,
) -> Iterator[CatalogMetadataStack]:
    # moto backends are process-global: every ThreadedMotoServer shares one
    # Glue store, so seed data leaks between tests unless reset each time.
    get_backend("glue").reset()
    register_catalog_metadata_handlers(
        data_catalog_store, GlueProxy.for_endpoint(live_moto_server.url)
    )
    glue = boto3.client(
        "glue",
        endpoint_url=live_moto_server.url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    athena = boto3.client(
        "athena",
        endpoint_url=live_athena_server.endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    yield CatalogMetadataStack(glue=glue, athena=athena)
    register_catalog_metadata_handlers(data_catalog_store)


def _seed_database(glue: BaseClient) -> None:
    glue.create_database(DatabaseInput=dict(CLI_SAMPLE_DATABASE))


def _seed_table(glue: BaseClient, name: str) -> None:
    glue.create_table(
        DatabaseName="sampledb",
        TableInput={
            "Name": name,
            "TableType": "EXTERNAL_TABLE",
            "StorageDescriptor": {
                "Columns": [
                    {"Name": "name", "Type": "string", "Comment": "geo id"},
                    {"Name": "population", "Type": "bigint", "Comment": ""},
                ]
            },
            "PartitionKeys": [{"Name": "region", "Type": "string"}],
            "Parameters": {"EXTERNAL": "TRUE", "location": "s3://bucket/json"},
        },
    )


def test_list_databases_matches_cli_example(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    stack = catalog_metadata_stack
    _seed_database(stack.glue)

    response = stack.athena.list_databases(CatalogName="AwsDataCatalog")

    assert response["DatabaseList"] == [CLI_SAMPLE_DATABASE]
    assert "NextToken" not in response


def test_get_database_matches_cli_example(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    stack = catalog_metadata_stack
    _seed_database(stack.glue)

    database = stack.athena.get_database(
        CatalogName="AwsDataCatalog", DatabaseName="sampledb"
    )["Database"]

    assert database == CLI_SAMPLE_DATABASE


def test_get_db_and_table_created_elsewhere_are_visible_to_the_api(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    # ADR-0005 single-store parity: what the engine sees (Glue) is what the
    # API returns — nothing to sync.
    stack = catalog_metadata_stack
    _seed_database(stack.glue)
    _seed_table(stack.glue, "counties")

    metadata = stack.athena.get_table_metadata(
        CatalogName="AwsDataCatalog",
        DatabaseName="sampledb",
        TableName="counties",
    )["TableMetadata"]

    assert metadata["Name"] == "counties"
    assert metadata["TableType"] == "EXTERNAL_TABLE"
    assert metadata["Columns"] == [
        {"Name": "name", "Type": "string", "Comment": "geo id"},
        {"Name": "population", "Type": "bigint", "Comment": ""},
    ]
    assert metadata["PartitionKeys"] == [{"Name": "region", "Type": "string"}]
    assert metadata["Parameters"]["location"] == "s3://bucket/json"
    assert isinstance(metadata["CreateTime"], datetime)
    assert isinstance(metadata["LastAccessTime"], datetime)


def test_list_table_metadata_filters_and_paginates(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    stack = catalog_metadata_stack
    _seed_database(stack.glue)
    for name in ["countries", "cities", "orders"]:
        _seed_table(stack.glue, name)

    first = stack.athena.list_table_metadata(
        CatalogName="AwsDataCatalog",
        DatabaseName="sampledb",
        Expression="c.*",
        MaxResults=1,
    )
    assert [item["Name"] for item in first["TableMetadataList"]] == [
        "countries"
    ]
    assert "NextToken" in first

    second = stack.athena.list_table_metadata(
        CatalogName="AwsDataCatalog",
        DatabaseName="sampledb",
        Expression="c.*",
        MaxResults=1,
        NextToken=first["NextToken"],
    )
    assert [item["Name"] for item in second["TableMetadataList"]] == ["cities"]
    assert "NextToken" not in second


def test_get_database_missing_is_shaped_metadata_400(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    stack = catalog_metadata_stack

    with pytest.raises(ClientError) as exc_info:
        stack.athena.get_database(
            CatalogName="AwsDataCatalog", DatabaseName="missing"
        )

    error = exc_info.value.response["Error"]
    assert error["Code"] == "MetadataException"
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "missing" in error["Message"]


def test_get_table_metadata_missing_is_shaped_metadata_400(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    stack = catalog_metadata_stack
    _seed_database(stack.glue)

    with pytest.raises(ClientError) as exc_info:
        stack.athena.get_table_metadata(
            CatalogName="AwsDataCatalog",
            DatabaseName="sampledb",
            TableName="missing",
        )

    error = exc_info.value.response["Error"]
    assert error["Code"] == "MetadataException"
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "missing" in error["Message"]


def test_unknown_catalog_is_shaped_invalid_request_400(
    catalog_metadata_stack: CatalogMetadataStack,
) -> None:
    stack = catalog_metadata_stack

    with pytest.raises(ClientError) as exc_info:
        stack.athena.list_databases(CatalogName="missing-catalog")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert exc_info.value.response["ResponseMetadata"]["HTTPStatusCode"] == 400
    assert "missing-catalog" in error["Message"]
