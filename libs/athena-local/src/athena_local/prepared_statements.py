"""Prepared statement operations (MD-3): handlers bound into the dispatch registry.

Each handler parses its request payload against the typed schemas, delegates
registry semantics to ``PreparedStatementStore``, and returns the operation's
output object. Registration is explicit (composition root: ``main.py``) so handlers
stay injectable and tests bind their own store.

The key difference from named queries: ``GetPreparedStatement`` raises
``ResourceNotFoundException`` for missing statements per awswrangler expectations
(``research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29``).
"""

from __future__ import annotations

from typing import cast

from athena_local.dispatch import register_handler
from athena_local.errors import InvalidRequestException
from athena_local.state import PreparedStatementStore


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


def create_prepared_statement(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    statement_name = _required_string(payload, "StatementName")
    workgroup = _required_string(payload, "WorkGroup")
    query_statement = _required_string(payload, "QueryStatement")
    description = _optional_string(payload, "Description")
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
    statement_name = _required_string(payload, "StatementName")
    workgroup = _required_string(payload, "WorkGroup")
    record = store.get(statement_name, workgroup)
    return {"PreparedStatement": record.to_payload()}


def list_prepared_statements(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    workgroup = _required_string(payload, "WorkGroup")
    max_results = None
    if _member(payload, "MaxResults") is not None:
        max_results = _required_int(payload, "MaxResults")
    next_token = _optional_string(payload, "NextToken")
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
    statement_name = _required_string(payload, "StatementName")
    workgroup = _required_string(payload, "WorkGroup")
    query_statement = _required_string(payload, "QueryStatement")
    description = _optional_string(payload, "Description")
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
    statement_name = _required_string(payload, "StatementName")
    workgroup = _required_string(payload, "WorkGroup")
    store.delete(statement_name, workgroup)
    return {}


def batch_get_prepared_statement(
    store: PreparedStatementStore, payload: dict[str, object] | None
) -> dict[str, object]:
    statement_names = _required_string_list(payload, "PreparedStatementNames")
    workgroup = _required_string(payload, "WorkGroup")
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
) -> None:
    """Bind the six prepared statement operations to ``store`` (explicit wiring)."""
    register_handler(
        "CreatePreparedStatement",
        lambda payload: create_prepared_statement(store, payload),
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
