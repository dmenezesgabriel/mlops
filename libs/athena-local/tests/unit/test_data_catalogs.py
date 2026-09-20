"""Handler tests for the five data catalog operations (MD-4).

Handlers translate a parsed JSON payload into the operation's output shape,
delegating registry semantics to ``DataCatalogStore``. The wire contract
(``DataCatalog``/``DataCatalogSummary`` members, ``DataCatalogType`` enum)
comes from the canonical service-2.json; LAMBDA parameter normalization mirrors
the documented AWS behavior in the CLI ``get-data-catalog`` example.
"""

from __future__ import annotations

import pytest
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.data_catalogs import (
    create_data_catalog,
    delete_data_catalog,
    get_data_catalog,
    list_data_catalogs,
    update_data_catalog,
)
from athena_local.dispatch import implemented_operations
from athena_local.errors import InvalidRequestException

DATA_CATALOG_OPERATIONS = {
    "CreateDataCatalog",
    "GetDataCatalog",
    "ListDataCatalogs",
    "UpdateDataCatalog",
    "DeleteDataCatalog",
}


@pytest.fixture()
def store() -> DataCatalogStore:
    return DataCatalogStore()


def test_data_catalog_operations_are_registered() -> None:
    # main.py is the composition root (ADR-0003); importing it registers the
    # five data catalog operations against the app's store exactly once.
    import athena_local.main  # noqa: F401

    assert DATA_CATALOG_OPERATIONS <= implemented_operations()


def test_aws_data_catalog_is_seeded(store: DataCatalogStore) -> None:
    # Every AWS account has a Glue-backed AwsDataCatalog; list-data-catalogs.rst
    # shows it present without any registration.
    catalog = store.get("AwsDataCatalog")
    assert catalog.catalog_type == "GLUE"


def test_create_glue_data_catalog_returns_payload(
    store: DataCatalogStore,
) -> None:
    output = create_data_catalog(
        store,
        {
            "Name": "glue_catalog",
            "Type": "GLUE",
            "Description": "Main Glue catalog",
        },
    )

    catalog = output["DataCatalog"]
    assert catalog["Name"] == "glue_catalog"
    assert catalog["Type"] == "GLUE"
    assert catalog["Description"] == "Main Glue catalog"
    record = store.get("glue_catalog")
    assert record.parameters == {}


def test_create_data_catalog_requires_name(store: DataCatalogStore) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        create_data_catalog(store, {"Type": "GLUE"})


def test_create_data_catalog_requires_type(store: DataCatalogStore) -> None:
    with pytest.raises(InvalidRequestException, match="Type"):
        create_data_catalog(store, {"Name": "glue_catalog"})


def test_create_data_catalog_rejects_unknown_type(
    store: DataCatalogStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Type"):
        create_data_catalog(store, {"Name": "glue_catalog", "Type": "MAGIC"})


def test_create_data_catalog_rejects_federated_type(
    store: DataCatalogStore,
) -> None:
    # FEDERATED catalogs need the async connection/connector flow the
    # emulator does not implement; reject loudly rather than half-create.
    with pytest.raises(InvalidRequestException, match="FEDERATED"):
        create_data_catalog(
            store,
            {
                "Name": "federated_catalog",
                "Type": "FEDERATED",
                "Parameters": {"connector": "a.b"},
            },
        )


def test_create_data_catalog_duplicate_raises(
    store: DataCatalogStore,
) -> None:
    create_data_catalog(store, {"Name": "glue_catalog", "Type": "GLUE"})
    with pytest.raises(InvalidRequestException, match="already exists"):
        create_data_catalog(store, {"Name": "glue_catalog", "Type": "GLUE"})


def test_create_data_catalog_duplicate_of_seeded_raises(
    store: DataCatalogStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="already exists"):
        create_data_catalog(
            store, {"Name": "AwsDataCatalog", "Type": "LAMBDA"}
        )


def test_create_lambda_catalog_normalizes_parameters(
    store: DataCatalogStore,
) -> None:
    # AWS normalizes LAMBDA catalog Parameters on registration: the documented
    # get-data-catalog.rst example shows catalog=Name plus metadata-function and
    # record-function derived from the passed function value.
    output = create_data_catalog(
        store,
        {
            "Name": "dynamo_db_catalog",
            "Type": "LAMBDA",
            "Description": "DynamoDB Catalog",
            "Parameters": {
                "function": (
                    "arn:aws:lambda:us-west-2:111122223333:"
                    "function:dynamo_db_lambda"
                )
            },
        },
    )

    parameters = output["DataCatalog"]["Parameters"]
    assert parameters["catalog"] == "dynamo_db_catalog"
    assert parameters["metadata-function"] == (
        "arn:aws:lambda:us-west-2:111122223333:function:dynamo_db_lambda"
    )
    assert parameters["record-function"] == (
        "arn:aws:lambda:us-west-2:111122223333:function:dynamo_db_lambda"
    )


def test_create_lambda_catalog_keeps_explicit_overrides(
    store: DataCatalogStore,
) -> None:
    output = create_data_catalog(
        store,
        {
            "Name": "custom_catalog",
            "Type": "LAMBDA",
            "Parameters": {
                "function": "arn:aws:lambda:us-east-1:1:function:main",
                "metadata-function": "arn:aws:lambda:us-east-1:1:function:meta",
            },
        },
    )

    parameters = output["DataCatalog"]["Parameters"]
    assert parameters["metadata-function"] == (
        "arn:aws:lambda:us-east-1:1:function:meta"
    )
    assert parameters["record-function"] == (
        "arn:aws:lambda:us-east-1:1:function:main"
    )


def test_create_hive_catalog_keeps_parameters_as_passed(
    store: DataCatalogStore,
) -> None:
    output = create_data_catalog(
        store,
        {
            "Name": "hive_catalog",
            "Type": "HIVE",
            "Parameters": {
                "metadata-function": "arn:aws:lambda:us-east-1:1:function:meta",
                "skip-metadata": "false",
            },
        },
    )

    assert output["DataCatalog"]["Parameters"] == {
        "metadata-function": "arn:aws:lambda:us-east-1:1:function:meta",
        "skip-metadata": "false",
    }


def test_create_data_catalog_rejects_non_string_parameters(
    store: DataCatalogStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Parameters"):
        create_data_catalog(
            store,
            {
                "Name": "glue_catalog",
                "Type": "GLUE",
                "Parameters": {"function": 42},
            },
        )


def test_get_data_catalog_returns_seeded_catalog(
    store: DataCatalogStore,
) -> None:
    output = get_data_catalog(store, {"Name": "AwsDataCatalog"})
    assert output["DataCatalog"]["Name"] == "AwsDataCatalog"
    assert output["DataCatalog"]["Type"] == "GLUE"


def test_get_data_catalog_missing_raises_invalid_request(
    store: DataCatalogStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_data_catalog(store, {"Name": "missing_catalog"})


def test_get_data_catalog_requires_name(store: DataCatalogStore) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        get_data_catalog(store, None)


def test_list_data_catalogs_includes_seeded_catalog(
    store: DataCatalogStore,
) -> None:
    output = list_data_catalogs(store, None)
    assert {"CatalogName": "AwsDataCatalog", "Type": "GLUE"} in output[
        "DataCatalogsSummary"
    ]


def test_list_data_catalogs_with_pagination(store: DataCatalogStore) -> None:
    for i in range(5):
        create_data_catalog(store, {"Name": f"catalog{i}", "Type": "GLUE"})

    # The seeded AwsDataCatalog counts too, so 6 records paginate
    # 2/2/2 — page3 holds the last two and ends the token chain.
    page1 = list_data_catalogs(store, {"MaxResults": 2})
    assert len(page1["DataCatalogsSummary"]) == 2
    assert "NextToken" in page1

    page2 = list_data_catalogs(
        store, {"MaxResults": 2, "NextToken": page1["NextToken"]}
    )
    assert len(page2["DataCatalogsSummary"]) == 2
    assert "NextToken" in page2

    page3 = list_data_catalogs(
        store, {"MaxResults": 2, "NextToken": page2["NextToken"]}
    )
    assert len(page3["DataCatalogsSummary"]) == 2
    assert "NextToken" not in page3


def test_list_data_catalogs_invalid_next_token_raises(
    store: DataCatalogStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_data_catalogs(store, {"NextToken": "garbage"})


def test_update_data_catalog_replaces_fields(
    store: DataCatalogStore,
) -> None:
    create_data_catalog(
        store,
        {
            "Name": "cw_logs_catalog",
            "Type": "LAMBDA",
            "Description": "Old description",
            "Parameters": {
                "function": "arn:aws:lambda:us-west-2:1:function:old"
            },
        },
    )

    output = update_data_catalog(
        store,
        {
            "Name": "cw_logs_catalog",
            "Type": "LAMBDA",
            "Description": "New CloudWatch Logs Catalog",
            "Parameters": {
                "function": "arn:aws:lambda:us-west-2:1:function:new"
            },
        },
    )
    # UpdateDataCatalog responds with no output members beyond the modeled
    # optional ones; the update is visible through Get.
    assert "DataCatalog" not in output
    catalog = store.get("cw_logs_catalog")
    assert catalog.description == "New CloudWatch Logs Catalog"
    assert catalog.parameters["function"] == (
        "arn:aws:lambda:us-west-2:1:function:new"
    )


def test_update_data_catalog_requires_type(store: DataCatalogStore) -> None:
    create_data_catalog(store, {"Name": "cw_logs_catalog", "Type": "LAMBDA"})
    with pytest.raises(InvalidRequestException, match="Type"):
        update_data_catalog(store, {"Name": "cw_logs_catalog"})


def test_update_data_catalog_missing_raises(store: DataCatalogStore) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        update_data_catalog(
            store, {"Name": "missing_catalog", "Type": "LAMBDA"}
        )


def test_delete_data_catalog_returns_deleted_payload(
    store: DataCatalogStore,
) -> None:
    create_data_catalog(store, {"Name": "UnusedDataCatalog", "Type": "HIVE"})

    output = delete_data_catalog(store, {"Name": "UnusedDataCatalog"})

    assert output["DataCatalog"]["Name"] == "UnusedDataCatalog"
    with pytest.raises(InvalidRequestException, match="does not exist"):
        store.get("UnusedDataCatalog")


def test_delete_data_catalog_missing_raises(store: DataCatalogStore) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        delete_data_catalog(store, {"Name": "missing_catalog"})


def test_delete_data_catalog_requires_name(store: DataCatalogStore) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        delete_data_catalog(store, {})
