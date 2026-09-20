"""Step definitions for the data catalog BDD feature (MD-4).

Steps exercise the handler layer directly against a fresh in-memory registry
per scenario — the same boundary pytest-bdd asserts for the canonical model —
so the feature runs without HTTP or docker while pinning the JSON-1.1 wire
behavior consumers depend on.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.data_catalogs import (
    create_data_catalog,
    delete_data_catalog,
    get_data_catalog,
    list_data_catalogs,
    update_data_catalog,
)
from athena_local.errors import AthenaError, InvalidRequestException
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("data_catalogs.feature")


@dataclass
class DataCatalogOutcome:
    """State shared between the when and then steps of a scenario."""

    error: AthenaError | None = None
    last_success: dict[str, object] | None = None
    created_names: list[str] = None
    next_token: str | None = None


@pytest.fixture
def data_catalog_store() -> DataCatalogStore:
    return DataCatalogStore()


@pytest.fixture
def outcome() -> DataCatalogOutcome:
    return DataCatalogOutcome(created_names=[])


@given("a fresh data catalog registry")
def _fresh_registry(
    data_catalog_store: DataCatalogStore, outcome: DataCatalogOutcome
) -> None:
    assert list(data_catalog_store.by_name) == ["AwsDataCatalog"]
    outcome.created_names = []
    outcome.next_token = None


@given("the pre-registered AwsDataCatalog")
def _seeded_catalog() -> None:
    # The store fixture already seeds AwsDataCatalog; the step names the
    # precondition explicitly for scenario readability.
    pass


@when(parsers.parse('a GLUE data catalog named "{name}" is created'))
@when(
    parsers.parse(
        'a LAMBDA data catalog named "{name}" is created with function "{function}"'
    )
)
def _create_catalog(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    name: str,
    function: str | None = None,
) -> None:
    parameters = {}
    if function is not None:
        parameters = {"function": function}
    create_data_catalog(
        data_catalog_store,
        {
            "Name": name,
            "Type": "LAMBDA" if function is not None else "GLUE",
            "Parameters": parameters,
        },
    )
    outcome.created_names.append(name)


@when("GetDataCatalog targets the seeded catalog")
def _get_seeded_catalog(
    data_catalog_store: DataCatalogStore, outcome: DataCatalogOutcome
) -> None:
    outcome.last_success = get_data_catalog(
        data_catalog_store, {"Name": "AwsDataCatalog"}
    )


@when("GetDataCatalog targets a non-existent catalog")
def _get_missing_catalog(
    data_catalog_store: DataCatalogStore, outcome: DataCatalogOutcome
) -> None:
    try:
        get_data_catalog(data_catalog_store, {"Name": "missing-catalog"})
    except AthenaError as error:
        outcome.error = error


@when(parsers.parse('CreateDataCatalog targets the same name "{name}"'))
def _create_duplicate(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    name: str,
) -> None:
    try:
        create_data_catalog(data_catalog_store, {"Name": name, "Type": "GLUE"})
    except AthenaError as error:
        outcome.error = error


@when(parsers.parse("{num:d} data catalogs are created"))
def _create_multiple_catalogs(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    num: int,
) -> None:
    for i in range(num):
        create_data_catalog(
            data_catalog_store,
            {"Name": f"catalog{i}", "Type": "GLUE"},
        )
        outcome.created_names.append(f"catalog{i}")


@when(parsers.parse("ListDataCatalogs requests MaxResults {num:d}"))
def _list_with_max_results(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    num: int,
) -> None:
    outcome.last_success = list_data_catalogs(
        data_catalog_store, {"MaxResults": num}
    )


@when(
    parsers.parse(
        "ListDataCatalogs requests MaxResults {num:d} with the NextToken"
    )
)
def _list_with_next_token(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    num: int,
) -> None:
    outcome.last_success = list_data_catalogs(
        data_catalog_store,
        {"MaxResults": num, "NextToken": outcome.next_token},
    )


@when(
    parsers.parse('UpdateDataCatalog sets the description to "{description}"')
)
def _update_description(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    description: str,
) -> None:
    update_data_catalog(
        data_catalog_store,
        {
            "Name": outcome.created_names[0],
            "Type": "GLUE",
            "Description": description,
        },
    )


@when(parsers.parse('DeleteDataCatalog targets "{name}"'))
def _delete_catalog(
    data_catalog_store: DataCatalogStore,
    name: str,
) -> None:
    delete_data_catalog(data_catalog_store, {"Name": name})


@then(
    parsers.parse(
        'GetDataCatalog returns the catalog with type "{catalog_type}"'
    )
)
def _get_returns_type(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
    catalog_type: str,
) -> None:
    catalog = get_data_catalog(
        data_catalog_store, {"Name": outcome.created_names[0]}
    )["DataCatalog"]
    assert catalog["Type"] == catalog_type
    assert catalog["Name"] == outcome.created_names[0]


@then(parsers.parse('the catalog type is "{catalog_type}"'))
def _seeded_type(outcome: DataCatalogOutcome, catalog_type: str) -> None:
    catalog = outcome.last_success["DataCatalog"]
    assert catalog["Type"] == catalog_type


@then("ListDataCatalogs includes the seeded catalog")
def _list_includes_seeded(
    data_catalog_store: DataCatalogStore,
) -> None:
    summaries = list_data_catalogs(data_catalog_store, None)[
        "DataCatalogsSummary"
    ]
    assert {"CatalogName": "AwsDataCatalog", "Type": "GLUE"} in summaries


@then(
    "GetDataCatalog returns catalog-, metadata-function-, and record-function parameters"
)
def _lambda_parameters(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
) -> None:
    catalog = get_data_catalog(
        data_catalog_store, {"Name": outcome.created_names[0]}
    )["DataCatalog"]
    parameters = catalog["Parameters"]
    assert parameters["catalog"] == outcome.created_names[0]
    assert parameters["metadata-function"] == (
        "arn:aws:lambda:us-west-2:1:function:dynamo_db_lambda"
    )
    assert parameters["record-function"] == (
        "arn:aws:lambda:us-west-2:1:function:dynamo_db_lambda"
    )


@then("CreateDataCatalog answers InvalidRequestException")
@then("GetDataCatalog answers InvalidRequestException")
def _error_is_invalid_request(outcome: DataCatalogOutcome) -> None:
    assert isinstance(outcome.error, InvalidRequestException)


@then(parsers.parse("the response contains {num:d} catalog summaries"))
def _response_has_summaries(outcome: DataCatalogOutcome, num: int) -> None:
    assert len(outcome.last_success["DataCatalogsSummary"]) == num


@then("a NextToken is returned")
def _next_token_returned(outcome: DataCatalogOutcome) -> None:
    assert "NextToken" in outcome.last_success
    outcome.next_token = outcome.last_success["NextToken"]


@then("no NextToken is returned")
def _no_next_token(outcome: DataCatalogOutcome) -> None:
    assert "NextToken" not in outcome.last_success


@then("GetDataCatalog returns the updated description")
def _get_returns_updated_description(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
) -> None:
    catalog = get_data_catalog(
        data_catalog_store, {"Name": outcome.created_names[0]}
    )["DataCatalog"]
    assert catalog["Description"] == "New CloudWatch Logs Catalog"


@then("GetDataCatalog for the deleted catalog answers InvalidRequestException")
def _get_deleted_error(
    data_catalog_store: DataCatalogStore,
    outcome: DataCatalogOutcome,
) -> None:
    try:
        get_data_catalog(
            data_catalog_store, {"Name": outcome.created_names[0]}
        )
    except InvalidRequestException:
        pass
    else:
        raise AssertionError("Expected InvalidRequestException")
