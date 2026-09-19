"""Regression tests for the moto Glue overlay (docker/moto/glue_overlay.py).

Run with: `make -C docker/moto test`. Each case drives boto3 against moto's
in-process Glue backend through the same JSON-1.1 dispatch the server uses,
so the assertions cover wire shape and status parity, not just storage.
"""

import boto3
import pytest
from moto import mock_aws

import glue_overlay

glue_overlay.apply_overlay()

SAMPLE_STATISTICS = [
    {
        "ColumnName": "amount",
        "ColumnType": "BIGINT",
        "AnalyzedTime": 1767225600,
        "StatisticsData": {
            "Type": "LONG",
            "LongColumnStatisticsData": {
                "MinimumValue": 0,
                "MaximumValue": 10,
                "NumberOfNulls": 0,
                "NumberOfDistinctValues": 11,
            },
        },
    }
]


@mock_aws
def test_update_then_get_column_statistics_round_trip() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={
            "Name": "events",
            "StorageDescriptor": {
                "Columns": [{"Name": "amount", "Type": "bigint"}]
            },
        },
    )

    response = client.update_column_statistics_for_table(
        DatabaseName="analytics",
        TableName="events",
        ColumnStatisticsList=SAMPLE_STATISTICS,
    )
    assert set(response) == {"ResponseMetadata"}

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnNames=["amount"]
    )
    listed = response["ColumnStatisticsList"]
    assert len(listed) == 1
    assert listed[0]["ColumnName"] == "amount"
    assert listed[0]["StatisticsData"]["Type"] == "LONG"


@mock_aws
def test_delete_column_statistics_removes_entry() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )
    client.update_column_statistics_for_table(
        DatabaseName="analytics",
        TableName="events",
        ColumnStatisticsList=SAMPLE_STATISTICS,
    )

    response = client.delete_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnName="amount"
    )
    assert set(response) == {"ResponseMetadata"}

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnNames=["amount"]
    )
    assert response["ColumnStatisticsList"] == []


@mock_aws
def test_delete_unknown_column_is_idempotent() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    response = client.delete_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnName="missing"
    )
    assert set(response) == {"ResponseMetadata"}


@mock_aws
def test_update_statistics_unknown_table_raises_entity_not_found() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})

    with pytest.raises(Exception, match=r"EntityNotFoundException") as raised:
        client.update_column_statistics_for_table(
            DatabaseName="analytics",
            TableName="missing",
            ColumnStatisticsList=SAMPLE_STATISTICS,
        )
    assert raised.value.response["Error"]["Code"] == "EntityNotFoundException"


@mock_aws
def test_get_user_defined_functions_returns_empty_list() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})

    response = client.get_user_defined_functions(
        DatabaseName="analytics", Pattern="*"
    )
    assert response["UserDefinedFunctions"] == []


@mock_aws
def test_get_user_defined_functions_missing_database_raises() -> None:
    client = boto3.client("glue", region_name="us-east-1")

    with pytest.raises(Exception, match=r"EntityNotFoundException") as raised:
        client.get_user_defined_functions(
            DatabaseName="analytics", Pattern="*"
        )
    assert raised.value.response["Error"]["Code"] == "EntityNotFoundException"
