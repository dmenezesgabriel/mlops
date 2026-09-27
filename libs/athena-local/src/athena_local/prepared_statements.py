"""Prepared statement operations: handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``PreparedStatementStore``, and returns the operation's
output object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.

The key difference from named queries: ``GetPreparedStatement`` raises
``ResourceNotFoundException`` for missing statements per awswrangler expectations
(``research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29``).
"""

from __future__ import annotations

from athena_local.dispatch import register_handler
from athena_local.request_fields import (
    member,
    optional_string,
    required_int,
    required_string,
    required_string_list,
)
from athena_local.state import (
    PreparedStatementStore,
    WorkGroupStore,
    ensure_workgroup_enabled,
)


def create_prepared_statement(
    store: PreparedStatementStore,
    workgroup_store: WorkGroupStore,
    payload: dict[str, object] | None,
) -> dict[str, object]:
    statement_name = required_string(payload, "StatementName")
    workgroup = required_string(payload, "WorkGroup")
    ensure_workgroup_enabled(workgroup_store, workgroup)
    query_statement = required_string(payload, "QueryStatement")
    description = optional_string(payload, "Description")
    store.create(
        statement_name=statement_name,
        query_statement=query_statement,
        workgroup=workgroup,
        description=description,
    )
    return {}


def get_prepared_statement(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    statement_name = required_string(payload, "StatementName")
    workgroup = required_string(payload, "WorkGroup")
    record = store.get(statement_name, workgroup)
    return {"PreparedStatement": record.to_payload()}


def list_prepared_statements(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    workgroup = required_string(payload, "WorkGroup")
    max_results = None
    if member(payload, "MaxResults") is not None:
        max_results = required_int(payload, "MaxResults")
    next_token = optional_string(payload, "NextToken")
    statement_names, next_token_out = store.list(
        workgroup=workgroup,
        max_results=max_results,
        next_token=next_token,
    )
    output: dict[str, object] = {
        "PreparedStatements": [
            store.get(name, workgroup).to_summary_payload()
            for name in statement_names
        ]
    }
    if next_token_out is not None:
        output["NextToken"] = next_token_out
    return output


def update_prepared_statement(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    statement_name = required_string(payload, "StatementName")
    workgroup = required_string(payload, "WorkGroup")
    query_statement = required_string(payload, "QueryStatement")
    description = optional_string(payload, "Description")
    store.update(
        statement_name=statement_name,
        workgroup=workgroup,
        query_statement=query_statement,
        description=description,
    )
    return {}


def delete_prepared_statement(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    statement_name = required_string(payload, "StatementName")
    workgroup = required_string(payload, "WorkGroup")
    store.delete(statement_name, workgroup)
    return {}


def batch_get_prepared_statement(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    statement_names = required_string_list(payload, "PreparedStatementNames")
    workgroup = required_string(payload, "WorkGroup")
    found, unprocessed = store.batch_get(statement_names, workgroup)
    output: dict[str, object] = {
        "PreparedStatements": [record.to_payload() for record in found]
    }
    if unprocessed:
        output["UnprocessedPreparedStatementNames"] = [
            {"StatementName": name} for name in unprocessed
        ]
    return output


def register_prepared_statement_handlers(
    store: PreparedStatementStore,
    workgroup_store: WorkGroupStore,
) -> None:
    """Bind the six prepared statement operations to ``store`` (explicit wiring)."""
    register_handler(
        "CreatePreparedStatement",
        lambda payload: create_prepared_statement(
            store, workgroup_store, payload
        ),
    )
    register_handler(
        "GetPreparedStatement",
        lambda payload: get_prepared_statement(store, payload),
    )
    register_handler(
        "ListPreparedStatements",
        lambda payload: list_prepared_statements(store, payload),
    )
    register_handler(
        "UpdatePreparedStatement",
        lambda payload: update_prepared_statement(store, payload),
    )
    register_handler(
        "DeletePreparedStatement",
        lambda payload: delete_prepared_statement(store, payload),
    )
    register_handler(
        "BatchGetPreparedStatement",
        lambda payload: batch_get_prepared_statement(store, payload),
    )
