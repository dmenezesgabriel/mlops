"""Catalog-introspection operations reading live Glue state (MD-7).

ListDatabases / GetDatabase / ListTableMetadata / GetTableMetadata proxy reads
to the same moto Glue store Trino uses as its metastore (ADR-0005), so API
answers and engine views cannot diverge. The Glue boundary lives in
``glue_proxy``; these handlers parse the request, validate the named catalog,
paginate, and shape the Athena responses. Only GLUE-type data catalogs serve
database and table metadata — the proxy targets moto Glue, and federated
connector metadata stays out of scope (ADR-0004).
"""

from __future__ import annotations

import os

from athena_local.data_catalog_state import DataCatalogStore
from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.glue_proxy import GlueProxy

GLUE_CATALOG_TYPE = "GLUE"
MAX_LIST_DATABASES = 50
MAX_LIST_TABLE_METADATA = 50

MOTO_ENDPOINT_ENV = "ATHENA_MOTO_ENDPOINT_URL"
MOTO_ENDPOINT_DEFAULT = "http://127.0.0.1:5000"


def register_catalog_metadata_handlers(
    store: DataCatalogStore, proxy: GlueProxy | None = None
) -> None:
    """Bind the four catalog-introspection operations to ``store`` and ``proxy``.

    ``proxy`` defaults to the moto Glue endpoint named by
    ``ATHENA_MOTO_ENDPOINT_URL`` (fallback ``http://127.0.0.1:5000``, the
    compose moto port, ADR-0002); integration tests pass their own proxy so a
    test-scoped moto backs the reads.
    """
    bound = proxy
    if bound is None:
        bound = GlueProxy.for_endpoint(
            os.getenv(MOTO_ENDPOINT_ENV) or MOTO_ENDPOINT_DEFAULT
        )
    register_handler(
        "ListDatabases", lambda payload: list_databases(store, bound, payload)
    )
    register_handler(
        "GetDatabase", lambda payload: get_database(store, bound, payload)
    )
    register_handler(
        "ListTableMetadata",
        lambda payload: list_table_metadata(store, bound, payload),
    )
    register_handler(
        "GetTableMetadata",
        lambda payload: get_table_metadata(store, bound, payload),
    )


def list_databases(
    store: DataCatalogStore,
    proxy: GlueProxy,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    catalog_name = _required_string(payload, "CatalogName")
    _require_glue_catalog(store, catalog_name)
    max_results = _optional_max_results(
        payload, "MaxResults", MAX_LIST_DATABASES
    )
    next_token = _optional_string(payload, "NextToken")
    databases = [record.to_payload() for record in proxy.list_databases()]
    page, next_token_out = _paginate(databases, max_results, next_token)
    output: dict[str, object] = {"DatabaseList": page}
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


def get_database(
    store: DataCatalogStore,
    proxy: GlueProxy,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    catalog_name = _required_string(payload, "CatalogName")
    _require_glue_catalog(store, catalog_name)
    database_name = _required_string(payload, "DatabaseName")
    return {"Database": proxy.get_database(database_name).to_payload()}


def list_table_metadata(
    store: DataCatalogStore,
    proxy: GlueProxy,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    catalog_name = _required_string(payload, "CatalogName")
    _require_glue_catalog(store, catalog_name)
    database_name = _required_string(payload, "DatabaseName")
    expression = _optional_string(payload, "Expression")
    max_results = _optional_max_results(
        payload, "MaxResults", MAX_LIST_TABLE_METADATA
    )
    next_token = _optional_string(payload, "NextToken")
    tables = [
        record.to_payload()
        for record in proxy.list_tables(database_name, expression)
    ]
    page, next_token_out = _paginate(tables, max_results, next_token)
    output: dict[str, object] = {"TableMetadataList": page}
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


def get_table_metadata(
    store: DataCatalogStore,
    proxy: GlueProxy,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    catalog_name = _required_string(payload, "CatalogName")
    _require_glue_catalog(store, catalog_name)
    database_name = _required_string(payload, "DatabaseName")
    table_name = _required_string(payload, "TableName")
    return {
        "TableMetadata": proxy.get_table(
            database_name, table_name
        ).to_payload()
    }


def _member(payload: dict[str, object] | None, member: str) -> object | None:
    if payload is None:
        return None
    return payload.get(member)


def _required_string(payload: dict[str, object] | None, member: str) -> str:
    raw = _member(payload, member)
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidRequestException(
            f"{member} is required and must be a non-empty string, got {raw!r}"
        )
    return raw


def _optional_string(
    payload: dict[str, object] | None, member: str
) -> str | None:
    raw = _member(payload, member)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise InvalidRequestException(
            f"{member} must be a string, got {raw!r}"
        )
    return raw


def _optional_max_results(
    payload: dict[str, object] | None, member: str, maximum: int
) -> int | None:
    raw = _member(payload, member)
    if raw is None:
        return None
    if not isinstance(raw, int):
        raise InvalidRequestException(
            f"{member} must be an integer, got {raw!r}"
        )
    if raw < 1 or raw > maximum:
        raise InvalidRequestException(
            f"{member} must be between 1 and {maximum}, got {raw}"
        )
    return raw


def _require_glue_catalog(store: DataCatalogStore, catalog_name: str) -> None:
    # Unknown catalogs already answer InvalidRequestException from the store.
    record = store.get(catalog_name)
    if record.catalog_type != GLUE_CATALOG_TYPE:
        raise InvalidRequestException(
            f"DataCatalog {catalog_name} is of type {record.catalog_type}; "
            "only GLUE catalogs serve database and table metadata"
        )


def _paginate(
    items: list[dict[str, object]],
    max_results: int | None,
    next_token: str | None,
) -> tuple[list[dict[str, object]], str | None]:
    """Slice ``items`` like DataCatalogStore.list, over payload dicts.

    next_token is an integer offset rendered as ``str(index)``: opaque to
    consumers, trivially reversible for the emulator's in-memory read sets.
    """
    start_index = 0
    if next_token is not None:
        try:
            start_index = int(next_token)
        except ValueError:
            raise InvalidRequestException(
                f"Invalid NextToken: {next_token}"
            ) from None
    end_index = len(items)
    if max_results is not None:
        end_index = min(start_index + max_results, len(items))
    return items[start_index:end_index], (
        str(end_index) if end_index < len(items) else None
    )
