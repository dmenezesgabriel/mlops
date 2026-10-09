"""Named query operations: handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``NamedQueryStore``, and returns the operation's output
object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.
"""

from __future__ import annotations

from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.request_fields import (
    CLIENT_REQUEST_TOKEN_MAX_LENGTH,
    CLIENT_REQUEST_TOKEN_MIN_LENGTH,
    DATABASE_STRING_MAX_LENGTH,
    DESCRIPTION_STRING_MAX_LENGTH,
    DESCRIPTION_STRING_MIN_LENGTH,
    NAME_STRING_MAX_LENGTH,
    NAMED_QUERY_ID_MAX_LENGTH,
    NAMED_QUERY_ID_PATTERN,
    QUERY_STRING_MAX_LENGTH,
    WORKGROUP_NAME_PATTERN,
    optional_max_results,
    optional_string,
    required_string,
    required_string_list,
)
from athena_local.state import (
    NamedQueryRecord,
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
    name = required_string(payload, "Name", max_length=NAME_STRING_MAX_LENGTH)
    description = (
        optional_string(
            payload,
            "Description",
            min_length=DESCRIPTION_STRING_MIN_LENGTH,
            max_length=DESCRIPTION_STRING_MAX_LENGTH,
        )
        or ""
    )
    database = required_string(
        payload, "Database", max_length=DATABASE_STRING_MAX_LENGTH
    )
    query_string = required_string(
        payload, "QueryString", max_length=QUERY_STRING_MAX_LENGTH
    )
    workgroup = (
        optional_string(payload, "WorkGroup", pattern=WORKGROUP_NAME_PATTERN)
        or "primary"
    )
    client_request_token = optional_string(
        payload,
        "ClientRequestToken",
        min_length=CLIENT_REQUEST_TOKEN_MIN_LENGTH,
        max_length=CLIENT_REQUEST_TOKEN_MAX_LENGTH,
    )
    ensure_workgroup_enabled(workgroup_store, workgroup)
    record = _find_or_create(
        store,
        client_request_token,
        name=name,
        description=description,
        database=database,
        query_string=query_string,
        workgroup=workgroup,
    )
    return {"NamedQueryId": record.id}


def _find_or_create(
    store: NamedQueryStore,
    client_request_token: str | None,
    *,
    name: str,
    description: str,
    database: str,
    query_string: str,
    workgroup: str,
) -> NamedQueryRecord:
    """Replay the query a repeated ClientRequestToken names, else create one.

    The canonical model marks CreateNamedQuery idempotent (service-2.json):
    an identical retry answers the original NamedQueryId, while the same token
    with changed parameters errors.
    """
    if client_request_token is not None:
        existing = store.find_by_request_token(client_request_token)
        if existing is not None:
            if not existing.same_request(
                name=name,
                description=description,
                database=database,
                query_string=query_string,
                workgroup=workgroup,
            ):
                raise InvalidRequestException(
                    f"ClientRequestToken {client_request_token!r} was already "
                    "used with different request parameters"
                )
            return existing
    return store.create(
        name=name,
        description=description,
        database=database,
        query_string=query_string,
        workgroup=workgroup,
        client_request_token=client_request_token,
    )


def _named_query_id(payload: dict[str, object] | None) -> str:
    r"""Parse the model's NamedQueryId member (``\S+``, 1..128)."""
    return required_string(
        payload,
        "NamedQueryId",
        max_length=NAMED_QUERY_ID_MAX_LENGTH,
        pattern=NAMED_QUERY_ID_PATTERN,
    )


def get_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    record = store.get(_named_query_id(payload))
    return {"NamedQuery": record.to_payload()}


def list_named_queries(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    workgroup = (
        optional_string(payload, "WorkGroup", pattern=WORKGROUP_NAME_PATTERN)
        or "primary"
    )
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
    store.delete(_named_query_id(payload))
    return {}


def batch_get_named_query(
    store: NamedQueryStore, payload: dict[str, object] | None
) -> dict[str, object]:
    query_ids = required_string_list(
        payload,
        "NamedQueryIds",
        max_length=MAX_BATCH_NAMED_QUERIES,
        member_min_length=1,
        member_max_length=NAMED_QUERY_ID_MAX_LENGTH,
        member_pattern=NAMED_QUERY_ID_PATTERN,
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
