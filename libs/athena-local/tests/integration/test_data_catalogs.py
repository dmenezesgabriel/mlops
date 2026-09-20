"""Consumer-parity integration: real boto3 against the live app.

MD-4 acceptance check: the five data catalog operations round-trip through the
JSON-1.1 wire protocol using the ``LiveAthenaServer`` fixture, and the AWS CLI
data catalog examples (``create/get/list/delete-data-catalog.rst``) replay
against the emulator — including the LAMBDA parameter normalization the
``get-data-catalog`` example documents.
"""

from __future__ import annotations

import boto3
import pytest
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from tests.integration.conftest import LiveAthenaServer


def _client(endpoint_url: str) -> BaseClient:
    return boto3.client(
        "athena",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def test_data_catalog_crud_round_trip_with_botocore(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    create_response = client.create_data_catalog(
        Name="glue_catalog",
        Type="GLUE",
        Description="Main Glue catalog",
    )

    catalog = create_response["DataCatalog"]
    assert catalog["Name"] == "glue_catalog"
    assert catalog["Type"] == "GLUE"

    fetched = client.get_data_catalog(Name="glue_catalog")["DataCatalog"]
    assert fetched["Name"] == "glue_catalog"
    assert fetched["Type"] == "GLUE"
    assert fetched["Description"] == "Main Glue catalog"

    names = {
        summary["CatalogName"]
        for summary in client.list_data_catalogs()["DataCatalogsSummary"]
    }
    assert "glue_catalog" in names

    client.update_data_catalog(
        Name="glue_catalog",
        Type="GLUE",
        Description="Updated description",
    )
    fetched = client.get_data_catalog(Name="glue_catalog")["DataCatalog"]
    assert fetched["Description"] == "Updated description"

    deleted = client.delete_data_catalog(Name="glue_catalog")["DataCatalog"]
    assert deleted["Name"] == "glue_catalog"
    names = {
        summary["CatalogName"]
        for summary in client.list_data_catalogs()["DataCatalogsSummary"]
    }
    assert "glue_catalog" not in names


def test_aws_data_catalog_is_listed(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    summaries = client.list_data_catalogs()["DataCatalogsSummary"]

    assert {"CatalogName": "AwsDataCatalog", "Type": "GLUE"} in summaries
    fetched = client.get_data_catalog(Name="AwsDataCatalog")["DataCatalog"]
    assert fetched["Type"] == "GLUE"


def test_list_data_catalogs_paginates(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    for i in range(5):
        client.create_data_catalog(Name=f"catalog{i}", Type="GLUE")

    page1 = client.list_data_catalogs(MaxResults=2)
    assert len(page1["DataCatalogsSummary"]) == 2
    assert "NextToken" in page1

    page2 = client.list_data_catalogs(
        MaxResults=2, NextToken=page1["NextToken"]
    )
    assert len(page2["DataCatalogsSummary"]) == 2
    assert "NextToken" in page2

    page3 = client.list_data_catalogs(
        MaxResults=2, NextToken=page2["NextToken"]
    )
    assert len(page3["DataCatalogsSummary"]) == 2
    assert "NextToken" not in page3


def test_get_missing_data_catalog_is_shaped_400(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    with pytest.raises(ClientError) as exc_info:
        client.get_data_catalog(Name="missing-catalog")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "missing-catalog" in error["Message"]


def test_create_duplicate_data_catalog_is_shaped_400(
    live_athena_server: LiveAthenaServer,
) -> None:
    client = _client(live_athena_server.endpoint_url)

    client.create_data_catalog(Name="glue_catalog", Type="GLUE")
    with pytest.raises(ClientError) as exc_info:
        client.create_data_catalog(Name="glue_catalog", Type="GLUE")

    error = exc_info.value.response["Error"]
    assert error["Code"] == "InvalidRequestException"
    assert "already exists" in error["Message"]


def test_cli_create_and_get_data_catalog_example(
    live_athena_server: LiveAthenaServer,
) -> None:
    """Replay create-data-catalog.rst + get-data-catalog.rst.

    The documented example creates a LAMBDA catalog passing only ``function``;
    the documented Get output shows ``catalog``, ``metadata-function``, and
    ``record-function`` derived on registration. botocore requires the
    Parameter map as a dict, so the CLI's ``--parameters`` key=value pairs map
    to the same dict.
    """
    client = _client(live_athena_server.endpoint_url)

    client.create_data_catalog(
        Name="dynamo_db_catalog",
        Type="LAMBDA",
        Description="DynamoDB Catalog",
        Parameters={
            "function": (
                "arn:aws:lambda:us-west-2:111122223333:"
                "function:dynamo_db_lambda"
            )
        },
    )

    catalog = client.get_data_catalog(Name="dynamo_db_catalog")["DataCatalog"]
    assert catalog["Name"] == "dynamo_db_catalog"
    assert catalog["Description"] == "DynamoDB Catalog"
    assert catalog["Type"] == "LAMBDA"
    assert catalog["Parameters"]["catalog"] == "dynamo_db_catalog"
    assert catalog["Parameters"]["metadata-function"] == (
        "arn:aws:lambda:us-west-2:111122223333:function:dynamo_db_lambda"
    )
    assert catalog["Parameters"]["record-function"] == (
        "arn:aws:lambda:us-west-2:111122223333:function:dynamo_db_lambda"
    )


def test_cli_update_data_catalog_example(
    live_athena_server: LiveAthenaServer,
) -> None:
    """Replay update-data-catalog.rst: replaces the function and description."""
    client = _client(live_athena_server.endpoint_url)

    client.create_data_catalog(
        Name="cw_logs_catalog",
        Type="LAMBDA",
        Description="CloudWatch Logs Catalog",
        Parameters={"function": "arn:aws:lambda:us-east-1:1:function:old"},
    )
    client.update_data_catalog(
        Name="cw_logs_catalog",
        Type="LAMBDA",
        Description="New CloudWatch Logs Catalog",
        Parameters={
            "function": "arn:aws:lambda:us-east-1:1:function:new_cw_logs_lambda"
        },
    )

    catalog = client.get_data_catalog(Name="cw_logs_catalog")["DataCatalog"]
    assert catalog["Description"] == "New CloudWatch Logs Catalog"
    assert catalog["Parameters"]["metadata-function"] == (
        "arn:aws:lambda:us-east-1:1:function:new_cw_logs_lambda"
    )
