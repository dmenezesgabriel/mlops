"""Regression tests for the moto Glue overlay (docker/moto/glue_overlay.py).

Run with: `make -C docker/moto test`. Each case drives boto3 against moto's
in-process Glue backend through the same JSON-1.1 dispatch the server uses,
so the assertions cover wire shape and status parity, not just storage.
Member shapes boto3's serializer refuses outright are exercised with raw
HTTP posts against a real ``ThreadedMotoServer``.
"""

import http.client
import json

import boto3
import pytest
from moto import mock_aws
from moto.glue import utils as glue_utils
from moto.glue.models import GlueBackend
from moto.glue.responses import GlueResponse
from moto.glue.utils import _PartitionFilterExpressionCache
from moto.server import ThreadedMotoServer

import glue_overlay

glue_overlay.apply_overlay()


def _post_glue(
    port: int, action: str, payload: dict[str, object]
) -> tuple[int, bytes]:
    """POST a raw Glue JSON-1.1 request to a running moto server.

    Malformed member shapes — a string where a list belongs, a non-dict list
    entry — never reach the wire through boto3 because its serializer
    enforces the modeled shape client-side; only a raw HTTP caller exercises
    the handler's own validation.
    """
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(
        "POST",
        "/",
        body=json.dumps(payload),
        headers={
            "Content-Type": "application/x-amz-json-1.1",
            "X-Amz-Target": f"AWSGlue_20170331.{action}",
            # moto routes account/region off the credential scope; the
            # signature itself is never verified.
            "Authorization": (
                "AWS4-HMAC-SHA256 "
                "Credential=testing/20260101/us-east-1/glue/aws4_request, "
                "SignedHeaders=host;x-amz-date, Signature=testing"
            ),
        },
    )
    response = connection.getresponse()
    return response.status, response.read()


def _live_glue_client(port: int):
    return boto3.client(
        "glue",
        region_name="us-east-1",
        endpoint_url=f"http://127.0.0.1:{port}",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


@pytest.fixture
def moto_server():
    """A real moto HTTP server, for shapes boto3 cannot serialize."""
    server = ThreadedMotoServer("127.0.0.1", 0, verbose=False)
    server.start()
    _, port = server.get_host_and_port()
    yield port
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("POST", "/moto-api/reset")
    connection.getresponse().read()
    server.stop()


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


@mock_aws
def test_get_column_statistics_filters_to_column_names() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )
    quantity_statistics = [{**SAMPLE_STATISTICS[0], "ColumnName": "quantity"}]
    client.update_column_statistics_for_table(
        DatabaseName="analytics",
        TableName="events",
        ColumnStatisticsList=SAMPLE_STATISTICS + quantity_statistics,
    )

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics", TableName="events", ColumnNames=["amount"]
    )
    assert [
        stat["ColumnName"] for stat in response["ColumnStatisticsList"]
    ] == ["amount"]

    # Columns with no stored statistics are omitted, like real AWS.
    response = client.get_column_statistics_for_table(
        DatabaseName="analytics",
        TableName="events",
        ColumnNames=["amount", "ghost"],
    )
    assert [
        stat["ColumnName"] for stat in response["ColumnStatisticsList"]
    ] == ["amount"]

    response = client.get_column_statistics_for_table(
        DatabaseName="analytics",
        TableName="events",
        ColumnNames=["quantity", "amount"],
    )
    assert [
        stat["ColumnName"] for stat in response["ColumnStatisticsList"]
    ] == ["quantity", "amount"]


def test_get_column_statistics_missing_column_names_returns_400(
    moto_server,
) -> None:
    # ColumnNames is required in the Glue service model; a caller omitting it
    # must get a shaped 400, not the unfiltered store.
    client = _live_glue_client(moto_server)
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    status, body = _post_glue(
        moto_server,
        "GetColumnStatisticsForTable",
        {"DatabaseName": "analytics", "TableName": "events"},
    )

    assert status == 400
    assert b"InvalidInputException" in body


def test_get_column_statistics_non_list_column_names_returns_400(
    moto_server,
) -> None:
    client = _live_glue_client(moto_server)
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    status, body = _post_glue(
        moto_server,
        "GetColumnStatisticsForTable",
        {
            "DatabaseName": "analytics",
            "TableName": "events",
            "ColumnNames": "amount",
        },
    )

    assert status == 400
    assert b"InvalidInputException" in body


def test_get_column_statistics_non_str_column_name_returns_400(
    moto_server,
) -> None:
    client = _live_glue_client(moto_server)
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    status, body = _post_glue(
        moto_server,
        "GetColumnStatisticsForTable",
        {
            "DatabaseName": "analytics",
            "TableName": "events",
            "ColumnNames": [5],
        },
    )

    assert status == 400
    assert b"InvalidInputException" in body


def test_update_column_statistics_non_dict_entry_returns_400(
    moto_server,
) -> None:
    # A non-dict entry escapes call_action as a bare AttributeError → HTTP
    # 500 (werkzeug HTML page); real AWS returns a shaped 400 naming the bad
    # member.
    client = _live_glue_client(moto_server)
    client.create_database(DatabaseInput={"Name": "analytics"})
    client.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "events", "StorageDescriptor": {}},
    )

    status, body = _post_glue(
        moto_server,
        "UpdateColumnStatisticsForTable",
        {
            "DatabaseName": "analytics",
            "TableName": "events",
            "ColumnStatisticsList": [SAMPLE_STATISTICS[0], "bogus"],
        },
    )

    assert status == 400
    assert b"InvalidInputException" in body
    assert b"ColumnStatisticsList[1]" in body


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
def test_equality_filter_on_uppercase_varchar_partition_key() -> None:
    # AWS accepts "VARCHAR(2)" as a key type and the registered spelling
    # reaches the store verbatim; moto's _cast only knows bare lowercase
    # names, so the overlay's fold must normalize case and whitespace too.
    client = boto3.client("glue", region_name="us-east-1")
    database_name = "sales_db"
    table_name = "sales"
    _seed_partitioned_table(
        client,
        database_name,
        table_name,
        partition_keys=[{"Name": "region", "Type": "VARCHAR(2)"}],
        partition_values=[["US"], ["EU"]],
    )

    response = client.get_partitions(
        DatabaseName=database_name,
        TableName=table_name,
        Expression="region = 'EU'",
    )
    assert _partition_values_from(response) == [["EU"]]


@mock_aws
def test_equality_filter_on_spaced_decimal_partition_key() -> None:
    client = boto3.client("glue", region_name="us-east-1")
    database_name = "sales_db"
    table_name = "sales"
    _seed_partitioned_table(
        client,
        database_name,
        table_name,
        partition_keys=[{"Name": "amount", "Type": "decimal (10,2)"}],
        partition_values=[["10.50"], ["3.14"]],
    )

    response = client.get_partitions(
        DatabaseName=database_name,
        TableName=table_name,
        Expression="amount = 10.5",
    )
    assert _partition_values_from(response) == [["10.50"]]


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


def _detach_overlay() -> None:
    """Restore every moto attach point to its pre-overlay state."""
    for operation in glue_overlay._RESPONSE_OPERATIONS:
        try:
            delattr(GlueResponse, operation)
        except AttributeError:
            pass
    _PartitionFilterExpressionCache.get = (
        glue_overlay._ORIGINAL_FILTER_EXPRESSION_GET
    )
    glue_utils._cast = glue_overlay._ORIGINAL_PARTITION_CAST
    GlueBackend.create_table = glue_overlay._ORIGINAL_CREATE_TABLE
    GlueBackend.update_table = glue_overlay._ORIGINAL_UPDATE_TABLE
    GlueBackend.delete_table = glue_overlay._ORIGINAL_DELETE_TABLE
    GlueBackend.delete_database = glue_overlay._ORIGINAL_DELETE_DATABASE


def test_apply_overlay_attaches_remaining_bridges_after_upstream_drift() -> (
    None
):
    # A future moto shipping one of these operations natively must not
    # silence the rest: the single-attribute gate skipped every bridge on
    # exactly that drift. The sentinel doubles as proof a shipped op is
    # left alone rather than overwritten by the stub.
    _detach_overlay()
    sentinel = object()
    GlueResponse.get_user_defined_functions = sentinel
    try:
        glue_overlay.apply_overlay()

        for operation, handler in glue_overlay._RESPONSE_OPERATIONS.items():
            expected = (
                sentinel
                if operation == "get_user_defined_functions"
                else handler
            )
            assert getattr(GlueResponse, operation) is expected
        for owner, attribute, replacement in glue_overlay._PATCHES:
            assert getattr(owner, attribute) is replacement
    finally:
        if (
            getattr(GlueResponse, "get_user_defined_functions", None)
            is sentinel
        ):
            del GlueResponse.get_user_defined_functions
        glue_overlay.apply_overlay()
