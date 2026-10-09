"""Data catalog operations: handlers bound into the dispatch registry.

Each handler parses its request payload, delegates registry semantics to
``DataCatalogStore``, and returns the operation's output object. Registration
is explicit (composition root: ``main.py``) so handlers stay injectable.

Two AWS behaviors are pinned here from the CLI examples: LAMBDA catalogs get
their ``Parameters`` normalized on registration (``catalog`` plus
``metadata-function``/``record-function`` derived from ``function`` —
``create-data-catalog.rst`` creates with ``function``, ``get-data-catalog.rst``
reads the normalized set), and the FEDERATED type is unreachable behind real
AWS's async connector flow and rejects loudly here instead of half-creating.
"""

from __future__ import annotations

from athena_local.data_catalog_state import DataCatalogStore
from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.request_fields import (
    member,
    optional_max_results,
    optional_string,
    optional_string_map,
    required_string,
)
from athena_local.schemas import parse_tags

SUPPORTED_CATALOG_TYPES = ("GLUE", "HIVE", "LAMBDA")
UNSUPPORTED_CATALOG_TYPE = "FEDERATED"

# Canonical-model bound (service-2.json): MaxDataCatalogsCount 2..50.
MAX_LIST_DATA_CATALOGS = 50

# AWS normalizes LAMBDA catalog parameters: metadata-function and record-function
# fall back to the passed function value (get-data-catalog.rst example output).
LAMBDA_FUNCTION_KEY = "function"


def _validated_type(payload: dict[str, object] | None) -> str:
    raw = required_string(payload, "Type")
    if raw == UNSUPPORTED_CATALOG_TYPE:
        raise InvalidRequestException(
            "FEDERATED data catalogs are not supported by the emulator"
        )
    if raw not in SUPPORTED_CATALOG_TYPES:
        raise InvalidRequestException(
            f"Type must be one of {SUPPORTED_CATALOG_TYPES}, got {raw!r}"
        )
    return raw


def _apply_lambda_defaults(
    name: str, catalog_type: str, parameters: dict[str, str]
) -> dict[str, str]:
    if catalog_type != "LAMBDA":
        return parameters
    normalized = dict(parameters)
    if "catalog" not in normalized:
        normalized["catalog"] = name
    function_value = normalized.get(LAMBDA_FUNCTION_KEY)
    if function_value is not None:
        for key in ("metadata-function", "record-function"):
            if key not in normalized:
                normalized[key] = function_value
    return normalized


def create_data_catalog(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = required_string(payload, "Name")
    catalog_type = _validated_type(payload)
    parameters = optional_string_map(payload, "Parameters") or {}
    record = store.create(
        name=name,
        catalog_type=catalog_type,
        description=optional_string(payload, "Description"),
        parameters=_apply_lambda_defaults(name, catalog_type, parameters),
        tags=parse_tags(member(payload, "Tags")),
    )
    return {"DataCatalog": record.to_payload()}


def get_data_catalog(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = required_string(payload, "Name")
    return {"DataCatalog": store.get(name).to_payload()}


def list_data_catalogs(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    max_results = optional_max_results(
        payload, "MaxResults", MAX_LIST_DATA_CATALOGS, minimum=2
    )
    next_token = optional_string(payload, "NextToken")
    records, next_token_out = store.list(
        max_results=max_results, next_token=next_token
    )
    output: dict[str, object] = {
        "DataCatalogsSummary": [
            record.to_summary_payload() for record in records
        ]
    }
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


def update_data_catalog(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = required_string(payload, "Name")
    catalog_type = _validated_type(payload)
    parameters = optional_string_map(payload, "Parameters")
    if parameters is not None:
        parameters = _apply_lambda_defaults(name, catalog_type, parameters)
    store.update(
        name=name,
        catalog_type=catalog_type,
        description=optional_string(payload, "Description"),
        parameters=parameters,
    )
    return {}


def delete_data_catalog(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = required_string(payload, "Name")
    return {"DataCatalog": store.delete(name).to_payload()}


def register_data_catalog_handlers(store: DataCatalogStore) -> None:
    """Bind the five data catalog operations to ``store`` (explicit wiring)."""
    register_handler(
        "CreateDataCatalog",
        lambda payload: create_data_catalog(store, payload),
    )
    register_handler(
        "GetDataCatalog",
        lambda payload: get_data_catalog(store, payload),
    )
    register_handler(
        "ListDataCatalogs",
        lambda payload: list_data_catalogs(store, payload),
    )
    register_handler(
        "UpdateDataCatalog",
        lambda payload: update_data_catalog(store, payload),
    )
    register_handler(
        "DeleteDataCatalog",
        lambda payload: delete_data_catalog(store, payload),
    )
