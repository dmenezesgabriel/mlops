"""Data catalog operations (MD-4): handlers bound into the dispatch registry.

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

SUPPORTED_CATALOG_TYPES = ("GLUE", "HIVE", "LAMBDA")
UNSUPPORTED_CATALOG_TYPE = "FEDERATED"

# AWS normalizes LAMBDA catalog parameters: metadata-function and record-function
# fall back to the passed function value (get-data-catalog.rst example output).
LAMBDA_FUNCTION_KEY = "function"


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


def _required_int(payload: dict[str, object] | None, member: str) -> int:
    raw = _member(payload, member)
    if not isinstance(raw, int):
        raise InvalidRequestException(
            f"{member} must be an integer, got {raw!r}"
        )
    return raw


def _validated_type(payload: dict[str, object] | None) -> str:
    raw = _required_string(payload, "Type")
    if raw == UNSUPPORTED_CATALOG_TYPE:
        raise InvalidRequestException(
            "FEDERATED data catalogs are not supported by the emulator"
        )
    if raw not in SUPPORTED_CATALOG_TYPES:
        raise InvalidRequestException(
            f"Type must be one of {SUPPORTED_CATALOG_TYPES}, got {raw!r}"
        )
    return raw


def _optional_string_map(
    payload: dict[str, object] | None, member: str
) -> dict[str, str] | None:
    raw = _member(payload, member)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidRequestException(
            f"{member} must be an object of string pairs, got {raw!r}"
        )
    parameters: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise InvalidRequestException(
                f"{member} entries must map string to string, "
                f"got {key!r}: {value!r}"
            )
        parameters[key] = value
    return parameters


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
    name = _required_string(payload, "Name")
    catalog_type = _validated_type(payload)
    parameters = _optional_string_map(payload, "Parameters") or {}
    record = store.create(
        name=name,
        catalog_type=catalog_type,
        description=_optional_string(payload, "Description"),
        parameters=_apply_lambda_defaults(name, catalog_type, parameters),
    )
    return {"DataCatalog": record.to_payload()}


def get_data_catalog(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = _required_string(payload, "Name")
    return {"DataCatalog": store.get(name).to_payload()}


def list_data_catalogs(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    max_results = None
    if _member(payload, "MaxResults") is not None:
        max_results = _required_int(payload, "MaxResults")
    next_token = _optional_string(payload, "NextToken")
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
    name = _required_string(payload, "Name")
    catalog_type = _validated_type(payload)
    parameters = _optional_string_map(payload, "Parameters")
    if parameters is not None:
        parameters = _apply_lambda_defaults(name, catalog_type, parameters)
    store.update(
        name=name,
        catalog_type=catalog_type,
        description=_optional_string(payload, "Description"),
        parameters=parameters,
    )
    return {}


def delete_data_catalog(
    store: DataCatalogStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = _required_string(payload, "Name")
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
