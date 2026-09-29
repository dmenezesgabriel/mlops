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
def test_delete_table_purges_column_statistics() -> None:
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

    client.delete_table(DatabaseName="analytics", Name="events")
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnNames=["amount"]
    )
    assert response["ColumnStatisticsList"] == []


@mock_aws
def test_delete_database_purges_column_statistics() -> None:
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

    client.delete_database(Name="analytics")
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnNames=["amount"]
    )
    assert response["ColumnStatisticsList"] == []


@mock_aws
def test_batch_delete_table_purges_column_statistics() -> None:
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

    client.batch_delete_table(
        DatabaseName="analytics", TablesToDelete=["events"]
    )
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnNames=["amount"]
    )
    assert response["ColumnStatisticsList"] == []


@mock_aws
def test_statistics_store_does_not_grow_across_drop_cycles() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})
    stored_keys_before = sum(
        len(stores) for stores in glue_overlay._column_statistics.values()
    )
    for round_index in range(5):
        table_name = f"events_{round_index}"
        client.create_table(
            DatabaseName="analytics",
            TableInput={"Name": table_name, "StorageDescriptor": {}},
        )
        client.update_column_statistics_for_table(
            DatabaseName="analytics",
            TableName=table_name,
            ColumnStatisticsList=SAMPLE_STATISTICS,
        )
        client.delete_table(DatabaseName="analytics", Name=table_name)

    # The weak-keyed store can still pin entries for earlier tests' live
    # backends, so assert the delta this test produced, not an absolute.
    stored_keys_after = sum(
        len(stores) for stores in glue_overlay._column_statistics.values()
    )
    assert stored_keys_after == stored_keys_before


@mock_aws
def test_delete_without_statistics_store_succeeds() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    client.delete_table(DatabaseName="analytics", Name="events")
    client.delete_database(Name="analytics")


def _seed_partitioned_table(
    client,
    database_name: str,
    table_name: str,
    partition_keys: list[dict[str, str]],
    partition_values: list[list[str]],
) -> None:
    """Create a partitioned table and seed it with partitions."""
    client.create_database(DatabaseInput={"Name": database_name})
    client.create_table(
        DatabaseName=database_name,
        TableInput={
            "Name": table_name,
            "StorageDescriptor": {
                "Columns": [{"Name": "amount", "Type": "bigint"}],
                "Location": f"s3://bucket/{table_name}",
            },
            "PartitionKeys": partition_keys,
        },
    )
    for values in partition_values:
        client.create_partition(
            DatabaseName=database_name,
            TableName=table_name,
            PartitionInput={
                "Values": values,
                "StorageDescriptor": {
                    "Columns": [{"Name": "amount", "Type": "bigint"}],
                    "Location": f"s3://bucket/{table_name}/"
                    + "/".join(values),
                },
            },
        )


def _partition_values_from(response: dict[str, object]) -> list[list[str]]:
    """Extract the Values of each returned partition for compact assertions."""
    partitions = response["Partitions"]
    assert isinstance(partitions, list)
    return [partition["Values"] for partition in partitions]


@mock_aws
def test_empty_expression_returns_all_partitions() -> None:
    # Real AWS Glue treats a blank Expression as "no filter"; the Hive SDK v1
    # metastore client sends Expression='' when listing every partition. moto
    # 5.1.16 only special-cases None and fails the empty string (upstream fix
    # 4db88f3a4 / #10122), which breaks Trino partitioned reads.
    client = boto3.client("glue", region_name="us-east-1")
    database_name = "sales_db"
    table_name = "sales"
    _seed_partitioned_table(
        client,
        database_name,
        table_name,
        partition_keys=[{"Name": "region", "Type": "varchar(2)"}],
        partition_values=[["US"], ["EU"]],
    )

    for expression in ("", "   "):
        response = client.get_partitions(
            DatabaseName=database_name,
            TableName=table_name,
            Expression=expression,
        )
        assert _partition_values_from(response) == [["US"], ["EU"]]


@mock_aws
def test_equality_filter_on_varchar_partition_key() -> None:
    # Trino registers partition keys with their full Hive type spelling
    # (varchar(2)); moto's _cast only knows bare "varchar" and raised
    # "Unknown type : 'varchar(2)'" on any filtered GetPartitions.
    client = boto3.client("glue", region_name="us-east-1")
    database_name = "sales_db"
    table_name = "sales"
    _seed_partitioned_table(
        client,
        database_name,
        table_name,
        partition_keys=[{"Name": "region", "Type": "varchar(2)"}],
        partition_values=[["US"], ["EU"]],
    )

    response = client.get_partitions(
        DatabaseName=database_name,
        TableName=table_name,
        Expression="region = 'EU'",
    )
    assert _partition_values_from(response) == [["EU"]]


@mock_aws
def test_equality_filter_on_decimal_partition_key() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    database_name = "sales_db"
    table_name = "sales"
    _seed_partitioned_table(
        client,
        database_name,
        table_name,
        partition_keys=[{"Name": "amount", "Type": "decimal(10,2)"}],
        partition_values=[["10.50"], ["3.14"]],
    )

    response = client.get_partitions(
        DatabaseName=database_name,
        TableName=table_name,
        Expression="amount = 10.5",
    )
    assert _partition_values_from(response) == [["10.50"]]


@mock_aws
def test_equality_filter_on_double_partition_key() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    database_name = "sales_db"
    table_name = "sales"
    _seed_partitioned_table(
        client,
        database_name,
        table_name,
        partition_keys=[{"Name": "amount", "Type": "double"}],
        partition_values=[["3.14"], ["2.71"]],
    )

    response = client.get_partitions(
        DatabaseName=database_name,
        TableName=table_name,
        Expression="amount = 3.14",
    )
    assert _partition_values_from(response) == [["3.14"]]


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
