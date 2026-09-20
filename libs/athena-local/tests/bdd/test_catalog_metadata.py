"""Step definitions for the catalog metadata BDD feature (MD-7).

Steps drive the handler layer over a real ``GlueProxy`` built on the named
``FakeGlueClient`` (``tests/unit/_glue_fakes.py``), so the feature pins the
JSON-1.1 wire behavior consumers depend on without HTTP or docker — the same
boundary pytest-bdd asserts for every flow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from athena_local.catalog_metadata import (
    get_database,
    get_table_metadata,
    list_databases,
    list_table_metadata,
)
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.errors import (
    AthenaError,
    InvalidRequestException,
    MetadataException,
)
from athena_local.glue_proxy import GlueProxy
from pytest_bdd import given, parsers, scenarios, then, when
from tests.unit._glue_fakes import FakeGlueClient

scenarios("catalog_metadata.feature")


@dataclass
class CatalogMetadataOutcome:
    """State shared between the when and then steps of a scenario."""

    error: AthenaError | None = None
    last_success: dict[str, object] | None = None
    next_token: str | None = None
    created_tables: list[str] = field(default_factory=list)


@pytest.fixture
def catalog_store() -> DataCatalogStore:
    return DataCatalogStore()


@pytest.fixture
def fake_client() -> FakeGlueClient:
    return FakeGlueClient()


@pytest.fixture
def proxy(fake_client: FakeGlueClient) -> GlueProxy:
    return GlueProxy(fake_client)


@pytest.fixture
def outcome() -> CatalogMetadataOutcome:
    return CatalogMetadataOutcome()


@given("a fresh catalog registry with the Glue store")
def _fresh_registry(
    catalog_store: DataCatalogStore, outcome: CatalogMetadataOutcome
) -> None:
    assert list(catalog_store.by_name) == ["AwsDataCatalog"]
    outcome.error = None
    outcome.last_success = None
    outcome.next_token = None
    outcome.created_tables = []


@given(parsers.parse("the glue store contains databases {names}"))
def _seed_databases(fake_client: FakeGlueClient, names: str) -> None:
    for name in names.split(" and "):
        fake_client.databases.append({"Name": name})


@given(
    parsers.parse(
        'the glue store contains database "{name}" with description "{description}" and parameters {parameters}'
    )
)
def _seed_described_database(
    fake_client: FakeGlueClient, name: str, description: str, parameters: str
) -> None:
    parameter_map = {
        item.split("=")[0]: item.split("=")[1]
        for item in parameters.split(", ")
    }
    fake_client.databases.append(
        {"Name": name, "Description": description, "Parameters": parameter_map}
    )


@given(
    parsers.parse(
        'the glue store contains tables {tables} in database "{database}"'
    )
)
def _seed_tables(
    fake_client: FakeGlueClient, tables: str, database: str
) -> None:
    for name in re.split(r", | and ", tables):
        fake_client.tables.setdefault(database, []).append({"Name": name})


@given(
    parsers.parse(
        'the glue store contains table "{table}" in database "{database}" with columns, partition keys, and parameters'
    )
)
def _seed_full_table(
    fake_client: FakeGlueClient, table: str, database: str
) -> None:
    fake_client.tables[database] = [
        {
            "Name": table,
            "TableType": "EXTERNAL_TABLE",
            "CreateTime": datetime(2020, 7, 1, tzinfo=UTC),
            "StorageDescriptor": {
                "Columns": [
                    {"Name": "name", "Type": "string", "Comment": "geo id"},
                    {"Name": "population", "Type": "bigint", "Comment": ""},
                ]
            },
            "PartitionKeys": [{"Name": "region", "Type": "string"}],
            "Parameters": {"EXTERNAL": "TRUE", "location": "s3://bucket/json"},
        }
    ]


@when("ListDatabases targets the AwsDataCatalog catalog")
def _list_databases(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
) -> None:
    outcome.last_success = list_databases(
        catalog_store, proxy, {"CatalogName": "AwsDataCatalog"}
    )


@when(
    parsers.parse(
        'GetDatabase targets "{database}" in the AwsDataCatalog catalog'
    )
)
def _get_database(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
    database: str,
) -> None:
    outcome.last_success = get_database(
        catalog_store,
        proxy,
        {"CatalogName": "AwsDataCatalog", "DatabaseName": database},
    )


@when("GetDatabase targets a non-existent database")
def _get_missing_database(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
) -> None:
    try:
        get_database(
            catalog_store,
            proxy,
            {"CatalogName": "AwsDataCatalog", "DatabaseName": "missing"},
        )
    except AthenaError as error:
        outcome.error = error


@when("ListDatabases targets a non-existent catalog")
def _list_missing_catalog(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
) -> None:
    try:
        list_databases(
            catalog_store, proxy, {"CatalogName": "missing-catalog"}
        )
    except AthenaError as error:
        outcome.error = error


@when(
    parsers.parse(
        'ListTableMetadata targets database "{database}" with expression "{expression}" and MaxResults {max_results:d}'
    )
)
def _list_table_metadata(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
    database: str,
    expression: str,
    max_results: int,
) -> None:
    outcome.last_success = list_table_metadata(
        catalog_store,
        proxy,
        {
            "CatalogName": "AwsDataCatalog",
            "DatabaseName": database,
            "Expression": expression,
            "MaxResults": max_results,
        },
    )


@when(
    parsers.parse(
        'ListTableMetadata requests the next page for database "{database}" with expression "{expression}"'
    )
)
def _list_table_metadata_next(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
    database: str,
    expression: str,
) -> None:
    outcome.last_success = list_table_metadata(
        catalog_store,
        proxy,
        {
            "CatalogName": "AwsDataCatalog",
            "DatabaseName": database,
            "Expression": expression,
            "MaxResults": 1,
            "NextToken": outcome.next_token,
        },
    )


@when(
    parsers.parse(
        'GetTableMetadata targets table "{table}" in database "{database}"'
    )
)
def _get_table_metadata(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
    table: str,
    database: str,
) -> None:
    outcome.last_success = get_table_metadata(
        catalog_store,
        proxy,
        {
            "CatalogName": "AwsDataCatalog",
            "DatabaseName": database,
            "TableName": table,
        },
    )


@when("GetTableMetadata targets a non-existent table")
def _get_missing_table(
    catalog_store: DataCatalogStore,
    proxy: GlueProxy,
    outcome: CatalogMetadataOutcome,
) -> None:
    try:
        get_table_metadata(
            catalog_store,
            proxy,
            {
                "CatalogName": "AwsDataCatalog",
                "DatabaseName": "sampledb",
                "TableName": "missing",
            },
        )
    except AthenaError as error:
        outcome.error = error


@then(parsers.parse("the response lists the databases {names}"))
def _databases_listed(outcome: CatalogMetadataOutcome, names: str) -> None:
    expected = [{"Name": name} for name in names.split(" and ")]
    assert outcome.last_success["DatabaseList"] == expected


@then(
    parsers.parse(
        'the response is the database "{name}" with description and parameters'
    )
)
def _database_details(outcome: CatalogMetadataOutcome, name: str) -> None:
    assert outcome.last_success["Database"] == {
        "Name": name,
        "Description": "Sample database",
        "Parameters": {"CreatedBy": "Athena", "EXTERNAL": "TRUE"},
    }


@then(
    parsers.parse(
        'the response lists {count:d} table matching expression "{expression}"'
    )
)
def _tables_listed(
    outcome: CatalogMetadataOutcome, count: int, expression: str
) -> None:
    listed = outcome.last_success["TableMetadataList"]
    assert len(listed) == count
    assert all(re.match(expression, item["Name"]) for item in listed)


@then("a NextToken is returned")
def _next_token_returned(outcome: CatalogMetadataOutcome) -> None:
    assert "NextToken" in outcome.last_success
    outcome.next_token = outcome.last_success["NextToken"]


@then("no NextToken is returned")
def _no_next_token(outcome: CatalogMetadataOutcome) -> None:
    assert "NextToken" not in outcome.last_success


@then(
    "the response has name, table type, columns, partition keys, parameters, and a CreateTime"
)
def _full_table_shape(outcome: CatalogMetadataOutcome) -> None:
    table = outcome.last_success["TableMetadata"]
    assert table["Name"] == "counties"
    assert table["TableType"] == "EXTERNAL_TABLE"
    assert isinstance(table["CreateTime"], float)
    assert table["PartitionKeys"] == [{"Name": "region", "Type": "string"}]
    assert table["Parameters"]["EXTERNAL"] == "TRUE"


@then(parsers.parse("the table metadata lists columns {columns}"))
def _table_columns(outcome: CatalogMetadataOutcome, columns: str) -> None:
    names = [
        column["Name"]
        for column in outcome.last_success["TableMetadata"]["Columns"]
    ]
    assert names == columns.split(" and ")
    assert outcome.last_success["TableMetadata"]["Columns"][0]["Comment"] == (
        "geo id"
    )


@then("GetDatabase answers MetadataException")
@then("GetTableMetadata answers MetadataException")
def _error_is_metadata(outcome: CatalogMetadataOutcome) -> None:
    assert isinstance(outcome.error, MetadataException)


@then("ListDatabases answers InvalidRequestException")
def _error_is_invalid_request(outcome: CatalogMetadataOutcome) -> None:
    assert isinstance(outcome.error, InvalidRequestException)
