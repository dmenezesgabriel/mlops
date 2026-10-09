"""Handler tests for the catalog-introspection operations (ADR-0005).

ListDatabases / GetDatabase / ListTableMetadata / GetTableMetadata parse the
request, validate the named catalog against the emulator-owned registry, paginate,
and shape the Athena responses from the live Glue store (ADR-0005). These unit
tests drive the handlers over a named fake Glue client; the wire protocol
round-trip is covered by the integration suite.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from athena_local.catalog_metadata import (
    get_database,
    get_table_metadata,
    list_databases,
    list_table_metadata,
    register_catalog_metadata_handlers,
)
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.errors import (
    InvalidRequestException,
    MetadataException,
)
from athena_local.glue_proxy import GlueProxy
from tests.unit._glue_fakes import FakeGlueClient

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


@pytest.fixture()
def catalog_store() -> DataCatalogStore:
    return DataCatalogStore()


@pytest.fixture()
def fake_client() -> FakeGlueClient:
    return FakeGlueClient()


@pytest.fixture()
def proxy(fake_client: FakeGlueClient) -> GlueProxy:
    return GlueProxy(fake_client)


def test_list_databases_returns_database_list(catalog_store, proxy) -> None:
    proxy._client.databases.append(SAMPLE_DATABASE)

    output = list_databases(
        catalog_store, proxy, {"CatalogName": "AwsDataCatalog"}
    )

    assert output["DatabaseList"] == [
        {
            "Name": "sampledb",
            "Description": "Sample database",
            "Parameters": {"CreatedBy": "Athena", "EXTERNAL": "TRUE"},
        }
    ]


def test_list_databases_omits_absent_description_and_parameters(
    catalog_store, proxy
) -> None:
    proxy._client.databases.append({"Name": "default"})

    output = list_databases(
        catalog_store, proxy, {"CatalogName": "AwsDataCatalog"}
    )

    assert output["DatabaseList"] == [{"Name": "default"}]


def test_list_databases_paginates_with_max_results_and_next_token(
    catalog_store, proxy
) -> None:
    for index in range(3):
        proxy._client.databases.append({"Name": f"db{index}"})

    first = list_databases(
        catalog_store,
        proxy,
        {"CatalogName": "AwsDataCatalog", "MaxResults": 1},
    )
    assert first["DatabaseList"] == [{"Name": "db0"}]
    assert first["NextToken"] == "1"

    second = list_databases(
        catalog_store,
        proxy,
        {"CatalogName": "AwsDataCatalog", "MaxResults": 1, "NextToken": "1"},
    )
    assert second["DatabaseList"] == [{"Name": "db1"}]
    assert second["NextToken"] == "2"

    third = list_databases(
        catalog_store,
        proxy,
        {"CatalogName": "AwsDataCatalog", "MaxResults": 1, "NextToken": "2"},
    )
    assert third["DatabaseList"] == [{"Name": "db2"}]
    assert "NextToken" not in third


def test_list_databases_rejects_invalid_next_token(
    catalog_store, proxy
) -> None:
    with pytest.raises(InvalidRequestException):
        list_databases(
            catalog_store,
            proxy,
            {"CatalogName": "AwsDataCatalog", "NextToken": "not-an-int"},
        )


@pytest.mark.parametrize("max_results", [0, 51])
def test_list_databases_rejects_out_of_range_max_results(
    catalog_store, proxy, max_results: int
) -> None:
    with pytest.raises(InvalidRequestException):
        list_databases(
            catalog_store,
            proxy,
            {"CatalogName": "AwsDataCatalog", "MaxResults": max_results},
        )


def test_list_databases_missing_catalog_name(catalog_store, proxy) -> None:
    with pytest.raises(InvalidRequestException):
        list_databases(catalog_store, proxy, {})


def test_list_databases_unknown_catalog_is_rejected(
    catalog_store, proxy
) -> None:
    with pytest.raises(InvalidRequestException):
        list_databases(
            catalog_store, proxy, {"CatalogName": "missing-catalog"}
        )


def test_list_databases_non_glue_catalog_is_rejected(
    catalog_store, proxy
) -> None:
    catalog_store.create(
        name="lamba_catalog",
        catalog_type="LAMBDA",
        description=None,
        parameters={},
        tags=[],
    )

    with pytest.raises(InvalidRequestException):
        list_databases(catalog_store, proxy, {"CatalogName": "lamba_catalog"})


def test_get_database_returns_database(catalog_store, proxy) -> None:
    proxy._client.databases.append(SAMPLE_DATABASE)

    output = get_database(
        catalog_store,
        proxy,
        {"CatalogName": "AwsDataCatalog", "DatabaseName": "sampledb"},
    )

    assert output["Database"] == {
        "Name": "sampledb",
        "Description": "Sample database",
        "Parameters": {"CreatedBy": "Athena", "EXTERNAL": "TRUE"},
    }


def test_get_database_missing_name_is_rejected(catalog_store, proxy) -> None:
    with pytest.raises(InvalidRequestException):
        get_database(catalog_store, proxy, {"CatalogName": "AwsDataCatalog"})


def test_get_database_missing_database_is_metadata_exception(
    catalog_store, proxy
) -> None:
    with pytest.raises(MetadataException):
        get_database(
            catalog_store,
            proxy,
            {"CatalogName": "AwsDataCatalog", "DatabaseName": "missing"},
        )


def test_list_table_metadata_passes_expression_and_paginates(
    catalog_store, fake_client, proxy
) -> None:
    for name in ["countries", "cities", "orders"]:
        fake_client.tables.setdefault("geo", []).append({"Name": name})

    first = list_table_metadata(
        catalog_store,
        proxy,
        {
            "CatalogName": "AwsDataCatalog",
            "DatabaseName": "geo",
            "Expression": "c.*",
            "MaxResults": 1,
        },
    )
    assert [item["Name"] for item in first["TableMetadataList"]] == [
        "countries"
    ]
    assert first["NextToken"] == "1"

    second = list_table_metadata(
        catalog_store,
        proxy,
        {
            "CatalogName": "AwsDataCatalog",
            "DatabaseName": "geo",
            "Expression": "c.*",
            "MaxResults": 1,
            "NextToken": "1",
        },
    )
    assert [item["Name"] for item in second["TableMetadataList"]] == ["cities"]
    assert "NextToken" not in second

    assert fake_client.list_tables_calls == [
        {"DatabaseName": "geo", "Expression": "c.*"},
        {"DatabaseName": "geo", "Expression": "c.*"},
    ]


def test_list_table_metadata_missing_database_is_metadata_exception(
    catalog_store, proxy
) -> None:
    with pytest.raises(MetadataException):
        list_table_metadata(
            catalog_store,
            proxy,
            {"CatalogName": "AwsDataCatalog", "DatabaseName": "missing"},
        )


def test_get_table_metadata_returns_wire_shape(catalog_store, proxy) -> None:
    proxy._client.tables["geo"] = [SAMPLE_TABLE]

    output = get_table_metadata(
        catalog_store,
        proxy,
        {
            "CatalogName": "AwsDataCatalog",
            "DatabaseName": "geo",
            "TableName": "counties",
        },
    )

    assert output["TableMetadata"] == {
        "Name": "counties",
        "CreateTime": 1593561600.0,
        "LastAccessTime": 1593648000.0,
        "TableType": "EXTERNAL_TABLE",
        "Columns": [
            {
                "Name": "name",
                "Type": "string",
                "Comment": "from deserializer",
            },
            {"Name": "population", "Type": "int"},
        ],
        "PartitionKeys": [{"Name": "region", "Type": "string"}],
        "Parameters": {"EXTERNAL": "TRUE", "location": "s3://bucket/json"},
    }


def test_get_table_metadata_missing_table_name(catalog_store, proxy) -> None:
    with pytest.raises(InvalidRequestException):
        get_table_metadata(
            catalog_store,
            proxy,
            {"CatalogName": "AwsDataCatalog", "DatabaseName": "geo"},
        )


def test_get_table_metadata_missing_table_is_metadata_exception(
    catalog_store, proxy
) -> None:
    with pytest.raises(MetadataException):
        get_table_metadata(
            catalog_store,
            proxy,
            {
                "CatalogName": "AwsDataCatalog",
                "DatabaseName": "geo",
                "TableName": "missing",
            },
        )


def test_register_catalog_metadata_handlers_binds_four_operations(
    catalog_store, proxy
) -> None:
    register_catalog_metadata_handlers(catalog_store, proxy)

    from athena_local.dispatch import implemented_operations

    assert {
        "ListDatabases",
        "GetDatabase",
        "ListTableMetadata",
        "GetTableMetadata",
    }.issubset(implemented_operations())


@pytest.mark.parametrize(
    ("catalog_name", "match"),
    [("x" * 257, "at most 256"), ("\x00catalog", "must match pattern")],
)
def test_catalog_name_member_rejects_non_canonical_names(
    catalog_store, proxy, catalog_name: str, match: str
) -> None:
    # Model CatalogNameString: pattern [\u0020-\uD7FF…]*, 1..256
    # (service-2.json). Match the constraint message — the store's
    # "does not exist" would satisfy a bare "CatalogName" match.
    with pytest.raises(InvalidRequestException, match=match):
        list_databases(catalog_store, proxy, {"CatalogName": catalog_name})
    with pytest.raises(InvalidRequestException, match=match):
        get_database(
            catalog_store,
            proxy,
            {"CatalogName": catalog_name, "DatabaseName": "geo"},
        )
    with pytest.raises(InvalidRequestException, match=match):
        list_table_metadata(
            catalog_store,
            proxy,
            {"CatalogName": catalog_name, "DatabaseName": "geo"},
        )
    with pytest.raises(InvalidRequestException, match=match):
        get_table_metadata(
            catalog_store,
            proxy,
            {
                "CatalogName": catalog_name,
                "DatabaseName": "geo",
                "TableName": "t",
            },
        )


@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        (
            get_database,
            {"CatalogName": "AwsDataCatalog", "DatabaseName": "d" * 129},
        ),
        (
            list_table_metadata,
            {"CatalogName": "AwsDataCatalog", "DatabaseName": "d" * 129},
        ),
        (
            get_table_metadata,
            {
                "CatalogName": "AwsDataCatalog",
                "DatabaseName": "d" * 129,
                "TableName": "t",
            },
        ),
    ],
)
def test_database_name_member_rejects_oversized(
    catalog_store, proxy, operation, payload: dict[str, object]
) -> None:
    # Model NameString 1..128. Match the constraint message — a missing
    # database raises MetadataException from the proxy layer, which a bare
    # "DatabaseName" match cannot distinguish from a parse-layer check.
    with pytest.raises(InvalidRequestException, match="at most 128"):
        operation(catalog_store, proxy, payload)


def test_table_name_member_rejects_oversized(catalog_store, proxy) -> None:
    # Model NameString 1..128.
    with pytest.raises(InvalidRequestException, match="at most 128"):
        get_table_metadata(
            catalog_store,
            proxy,
            {
                "CatalogName": "AwsDataCatalog",
                "DatabaseName": "geo",
                "TableName": "t" * 129,
            },
        )
