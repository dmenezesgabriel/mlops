"""Step definitions for the prepared statement BDD feature (MD-3).

Steps exercise the handler layer directly against a fresh in-memory registry
per scenario — the same boundary pytest-bdd asserts for the canonical model —
so the feature runs without HTTP or docker while pinning the JSON-1.1 wire
behavior consumers depend on. Parametrized steps use ``parsers.parse`` so the
quoted values in the feature file are captured (pytest-bdd 8 no longer turns
plain step strings into capture patterns).

The key difference from named queries: GetPreparedStatement raises
ResourceNotFoundException for missing statements.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from athena_local.errors import (
    AthenaError,
    ResourceNotFoundException,
)
from athena_local.prepared_statements import (
    batch_get_prepared_statement,
    create_prepared_statement,
    delete_prepared_statement,
    get_prepared_statement,
    list_prepared_statements,
    update_prepared_statement,
)
from athena_local.state import PreparedStatementStore
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("prepared_statements.feature")


@dataclass
class PreparedStatementOutcome:
    """State shared between the when and then steps of a scenario."""

    error: AthenaError | None = None
    last_success: dict[str, object] | None = None
    created_names: list[str] = None
    next_token: str | None = None
    original_time: float | None = None


@pytest.fixture
def prepared_statement_store() -> PreparedStatementStore:
    return PreparedStatementStore()


@pytest.fixture
def outcome() -> PreparedStatementOutcome:
    return PreparedStatementOutcome(created_names=[])


@given("a fresh prepared statement registry")
def _fresh_registry(
    prepared_statement_store: PreparedStatementStore,
    outcome: PreparedStatementOutcome,
) -> None:
    assert prepared_statement_store.list("primary")[0] == []
    outcome.created_names = []
    outcome.next_token = None


@when(parsers.parse('a prepared statement named "{name}" is created'))
def _create_prepared_statement(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    name: str,
) -> None:
    create_prepared_statement(
        prepared_statement_store,
        {
            "StatementName": name,
            "WorkGroup": "primary",
            "QueryStatement": "SELECT * FROM flights",
        },
    )
    outcome.created_names.append(name)


@when(
    parsers.parse(
        'a prepared statement named "{name}" is created in the "{workgroup}" workgroup'
    )
)
def _create_prepared_statement_in_workgroup(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    name: str,
    workgroup: str,
) -> None:
    create_prepared_statement(
        prepared_statement_store,
        {
            "StatementName": name,
            "WorkGroup": workgroup,
            "QueryStatement": "SELECT * FROM flights",
        },
    )
    outcome.created_names.append(name)


@when(
    parsers.parse(
        'GetPreparedStatement targets a non-existent statement in "{workgroup}"'
    )
)
def _get_missing_statement(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    workgroup: str,
) -> None:
    try:
        get_prepared_statement(
            prepared_statement_store,
            {"StatementName": "missing-stmt", "WorkGroup": workgroup},
        )
    except AthenaError as error:
        outcome.error = error


@when(
    parsers.parse(
        '{num:d} prepared statements are created in the "{workgroup}" workgroup'
    )
)
def _create_multiple_statements(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    num: int,
    workgroup: str,
) -> None:
    for i in range(num):
        create_prepared_statement(
            prepared_statement_store,
            {
                "StatementName": f"stmt{i}",
                "WorkGroup": workgroup,
                "QueryStatement": f"SELECT {i}",
            },
        )
        outcome.created_names.append(f"stmt{i}")


@when(parsers.parse("ListPreparedStatements requests MaxResults {num:d}"))
def _list_with_max_results(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    num: int,
) -> None:
    outcome.last_success = list_prepared_statements(
        prepared_statement_store, {"WorkGroup": "analytics", "MaxResults": num}
    )


@when(
    parsers.parse(
        "ListPreparedStatements requests MaxResults {num:d} with the NextToken"
    )
)
def _list_with_next_token(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    num: int,
) -> None:
    outcome.last_success = list_prepared_statements(
        prepared_statement_store,
        {
            "WorkGroup": "analytics",
            "MaxResults": num,
            "NextToken": outcome.next_token,
        },
    )


@when(
    parsers.parse("UpdatePreparedStatement modifies the query and description")
)
def _update_statement(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    original_record = prepared_statement_store.get(
        outcome.created_names[0], "primary"
    )
    outcome.original_time = original_record.last_modified_time

    outcome.last_success = update_prepared_statement(
        prepared_statement_store,
        {
            "StatementName": outcome.created_names[0],
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 2",
            "Description": "Updated description",
        },
    )


@when(
    parsers.parse(
        'DeletePreparedStatement targets the created statement in "{workgroup}"'
    )
)
def _delete_created_statement(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    workgroup: str,
) -> None:
    delete_prepared_statement(
        prepared_statement_store,
        {"StatementName": outcome.created_names[0], "WorkGroup": workgroup},
    )


@given(parsers.parse("{num:d} prepared statements are created"))
@when(parsers.parse("{num:d} prepared statements are created"))
def _create_statements_without_workgroup(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    num: int,
) -> None:
    for i in range(num):
        create_prepared_statement(
            prepared_statement_store,
            {
                "StatementName": f"stmt{i}",
                "WorkGroup": "primary",
                "QueryStatement": f"SELECT {i}",
            },
        )
        outcome.created_names.append(f"stmt{i}")


@when(parsers.parse("{num:d} prepared statement is created"))
def _create_statement_singular(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    num: int,
) -> None:
    _create_statements_without_workgroup(
        outcome, prepared_statement_store, num
    )


@when(parsers.parse("BatchGetPreparedStatement requests both statement names"))
def _batch_get_both(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    outcome.last_success = batch_get_prepared_statement(
        prepared_statement_store,
        {
            "PreparedStatementNames": outcome.created_names,
            "WorkGroup": "primary",
        },
    )


@when(
    parsers.parse(
        "BatchGetPreparedStatement requests the created name and {num:d} missing names"
    )
)
def _batch_get_with_missing(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
    num: int,
) -> None:
    missing_names = [f"missing-{i}" for i in range(num)]
    outcome.last_success = batch_get_prepared_statement(
        prepared_statement_store,
        {
            "PreparedStatementNames": [outcome.created_names[0]]
            + missing_names,
            "WorkGroup": "primary",
        },
    )


@then("GetPreparedStatement returns the statement details")
def _get_returns_details(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    stmt = get_prepared_statement(
        prepared_statement_store,
        {"StatementName": outcome.created_names[0], "WorkGroup": "primary"},
    )["PreparedStatement"]
    assert stmt["StatementName"] == "flights_stmt"
    assert stmt["QueryStatement"] == "SELECT * FROM flights"


@then('the statement is scoped to the "primary" workgroup')
def _scoped_to_primary(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    stmt = get_prepared_statement(
        prepared_statement_store,
        {"StatementName": outcome.created_names[0], "WorkGroup": "primary"},
    )["PreparedStatement"]
    assert stmt["WorkGroupName"] == "primary"


@then('GetPreparedStatement returns the statement with workgroup "analytics"')
def _returns_analytics_workgroup(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    stmt = get_prepared_statement(
        prepared_statement_store,
        {"StatementName": outcome.created_names[0], "WorkGroup": "analytics"},
    )["PreparedStatement"]
    assert stmt["WorkGroupName"] == "analytics"


@then('ListPreparedStatements for "analytics" includes the statement')
def _list_includes_statement(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    stmts = list_prepared_statements(
        prepared_statement_store, {"WorkGroup": "analytics"}
    )["PreparedStatements"]
    names = {s["StatementName"] for s in stmts}
    assert outcome.created_names[0] in names


@then("GetPreparedStatement answers ResourceNotFoundException")
def _get_error_shape(outcome: PreparedStatementOutcome) -> None:
    assert isinstance(outcome.error, ResourceNotFoundException)


@then("the response contains 2 statements")
def _response_has_2_statements(outcome: PreparedStatementOutcome) -> None:
    assert len(outcome.last_success["PreparedStatements"]) == 2


@then("a NextToken is returned")
def _next_token_returned(outcome: PreparedStatementOutcome) -> None:
    assert "NextToken" in outcome.last_success
    outcome.next_token = outcome.last_success["NextToken"]


@then("the response contains 2 more statements")
def _response_has_2_more_statements(outcome: PreparedStatementOutcome) -> None:
    assert len(outcome.last_success["PreparedStatements"]) == 2


@then("the response contains 1 statement")
def _response_has_1_statement(outcome: PreparedStatementOutcome) -> None:
    assert len(outcome.last_success["PreparedStatements"]) == 1


@then("no NextToken is returned")
def _no_next_token(outcome: PreparedStatementOutcome) -> None:
    assert "NextToken" not in outcome.last_success


@then("GetPreparedStatement returns the updated query and description")
def _returns_updated(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    stmt = get_prepared_statement(
        prepared_statement_store,
        {"StatementName": outcome.created_names[0], "WorkGroup": "primary"},
    )["PreparedStatement"]
    assert stmt["QueryStatement"] == "SELECT 2"
    assert stmt["Description"] == "Updated description"


@then("LastModifiedTime has increased")
def _time_increased(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    assert outcome.original_time is not None
    current_record = prepared_statement_store.get(
        outcome.created_names[0], "primary"
    )
    assert current_record.last_modified_time > outcome.original_time


@then(
    "GetPreparedStatement for the deleted statement answers ResourceNotFoundException"
)
def _get_deleted_error(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    try:
        get_prepared_statement(
            prepared_statement_store,
            {
                "StatementName": outcome.created_names[0],
                "WorkGroup": "primary",
            },
        )
    except ResourceNotFoundException:
        pass
    else:
        raise AssertionError("Expected ResourceNotFoundException")


@then("ListPreparedStatements no longer includes the statement")
def _list_excludes_statement(
    outcome: PreparedStatementOutcome,
    prepared_statement_store: PreparedStatementStore,
) -> None:
    stmts = list_prepared_statements(
        prepared_statement_store, {"WorkGroup": "primary"}
    )["PreparedStatements"]
    names = {s["StatementName"] for s in stmts}
    assert outcome.created_names[0] not in names


@then("the response contains both PreparedStatement objects")
def _response_has_2_statements(outcome: PreparedStatementOutcome) -> None:
    assert len(outcome.last_success["PreparedStatements"]) == 2


@then("no UnprocessedPreparedStatementNames are returned")
def _no_unprocessed(outcome: PreparedStatementOutcome) -> None:
    assert "UnprocessedPreparedStatementNames" not in outcome.last_success


@then("the response contains 1 PreparedStatement object")
def _response_has_1_statement(outcome: PreparedStatementOutcome) -> None:
    assert len(outcome.last_success["PreparedStatements"]) == 1


@then("2 UnprocessedPreparedStatementNames are returned")
def _has_2_unprocessed(outcome: PreparedStatementOutcome) -> None:
    assert len(outcome.last_success["UnprocessedPreparedStatementNames"]) == 2
