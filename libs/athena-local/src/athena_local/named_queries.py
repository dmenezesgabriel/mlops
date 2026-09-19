"""Named query operations (MD-2): handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``NamedQueryStore``, and returns the operation's output
object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.
"""

from __future__ import annotations

from typing import cast

from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.state import NamedQueryStore


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


def _required_string_list(
    payload: dict[str, object] | None, member: str
) -> list[str]:
    raw = _member(payload, member)
    if not isinstance(raw, list):
        raise InvalidRequestException(f"{member} must be a list, got {raw!r}")
    if not raw:
        raise InvalidRequestException(f"{member} must not be empty")
    for item in raw:
        if not isinstance(item, str):
            raise InvalidRequestException(
                f"{member} must contain only strings, got {item!r}"
            )
    return cast(list[str], raw)


def create_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    name = _required_string(payload, "Name")
    description = _optional_string(payload, "Description") or ""
    database = _required_string(payload, "Database")
    query_string = _required_string(payload, "QueryString")
    workgroup = _optional_string(payload, "WorkGroup") or "primary"
    record = store.create(
        name=name,
        description=description,
        database=database,
        query_string=query_string,
        workgroup=workgroup,
    )
    return {"NamedQueryId": record.id}


def get_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_id = _required_string(payload, "NamedQueryId")
    record = store.get(query_id)
    return {"NamedQuery": record.to_payload()}


def list_named_queries(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    workgroup = _optional_string(payload, "WorkGroup") or "primary"
    max_results = None
    if _member(payload, "MaxResults") is not None:
        max_results = _required_int(payload, "MaxResults")
    next_token = _optional_string(payload, "NextToken")
    query_ids, next_token_out = store.list(
        workgroup=workgroup,
        max_results=max_results,
        next_token=next_token,
    )
    output: dict[str, object] = {"NamedQueryIds": query_ids}
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


def delete_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_id = _required_string(payload, "NamedQueryId")
    store.delete(query_id)
    return {}


def batch_get_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_ids = _required_string_list(payload, "NamedQueryIds")
    found, unprocessed = store.batch_get(query_ids)
    output: dict[str, object] = {
        "NamedQueries": [record.to_payload() for record in found]
    }
    if unprocessed:
        output["UnprocessedNamedQueryIds"] = [
            {"NamedQueryId": qid} for qid in unprocessed
        ]
    return output


def register_named_query_handlers(store: NamedQueryStore) -> None:
    """Bind the five named query operations to ``store`` (explicit wiring)."""
    register_handler(
        "CreateNamedQuery", lambda payload: create_named_query(store, payload)
    )
    register_handler(
        "GetNamedQuery", lambda payload: get_named_query(store, payload)
    )
    register_handler(
        "ListNamedQueries", lambda payload: list_named_queries(store, payload)
    )
    register_handler(
        "DeleteNamedQuery", lambda payload: delete_named_query(store, payload)
    )
    register_handler(
        "BatchGetNamedQuery",
        lambda payload: batch_get_named_query(store, payload),
    )
