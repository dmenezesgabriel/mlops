"""Named query operations: handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``NamedQueryStore``, and returns the operation's output
object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.
"""

from __future__ import annotations

from athena_local.dispatch import register_handler
from athena_local.request_fields import (
    optional_max_results,
    optional_string,
    required_string,
    required_string_list,
)
from athena_local.state import (
    NamedQueryStore,
    WorkGroupStore,
    ensure_workgroup_enabled,
)

# Canonical-model bounds (service-2.json): MaxNamedQueriesCount 0..50,
# NamedQueryIdList 1..50.
MAX_LIST_NAMED_QUERIES = 50
MAX_BATCH_NAMED_QUERIES = 50


def create_named_query(
    store: NamedQueryStore,
    workgroup_store: WorkGroupStore,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    name = required_string(payload, "Name")
    description = optional_string(payload, "Description") or ""
    database = required_string(payload, "Database")
    query_string = required_string(payload, "QueryString")
    workgroup = optional_string(payload, "WorkGroup") or "primary"
    ensure_workgroup_enabled(workgroup_store, workgroup)
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
    query_id = required_string(payload, "NamedQueryId")
    record = store.get(query_id)
    return {"NamedQuery": record.to_payload()}


def list_named_queries(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    workgroup = optional_string(payload, "WorkGroup") or "primary"
    max_results = optional_max_results(
        payload, "MaxResults", MAX_LIST_NAMED_QUERIES, minimum=0
    )
    next_token = optional_string(payload, "NextToken")
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
    query_id = required_string(payload, "NamedQueryId")
    store.delete(query_id)
    return {}


def batch_get_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_ids = required_string_list(
        payload, "NamedQueryIds", max_length=MAX_BATCH_NAMED_QUERIES
    )
    found, unprocessed = store.batch_get(query_ids)
    output: dict[str, object] = {
        "NamedQueries": [record.to_payload() for record in found]
    }
    if unprocessed:
        output["UnprocessedNamedQueryIds"] = [
            {"NamedQueryId": qid} for qid in unprocessed
        ]
    return output


def register_named_query_handlers(
    store: NamedQueryStore, workgroup_store: WorkGroupStore
) -> None:
    """Bind the five named query operations to ``store`` (explicit wiring)."""
    register_handler(
        "CreateNamedQuery",
        lambda payload: create_named_query(store, workgroup_store, payload),
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
