"""Handler tests for the six prepared statement operations (MD-3).

Handlers translate a parsed JSON payload into the operation's output shape,
delegating registry semantics to ``PreparedStatementStore``. The payload-shape
contract lives in the service model; these tests fix the wire-facing behavior:
output keys match the canonical service-2.json output members.

The key difference from named queries: ``GetPreparedStatement`` raises
``ResourceNotFoundException`` for missing statements per awswrangler expectations
(``research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29``).
"""

from __future__ import annotations

import pytest
from athena_local.dispatch import implemented_operations
from athena_local.errors import (
    InvalidRequestException,
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

PREPARED_STATEMENT_OPERATIONS = {
    "CreatePreparedStatement",
    "GetPreparedStatement",
    "ListPreparedStatements",
    "UpdatePreparedStatement",
    "DeletePreparedStatement",
    "BatchGetPreparedStatement",
}


@pytest.fixture()
def store() -> PreparedStatementStore:
    return PreparedStatementStore()


def test_prepared_statement_operations_are_registered() -> None:
    # main.py is the composition root (ADR-0003); importing it registers the
    # six prepared statement operations against the app's store exactly once.
    import athena_local.main  # noqa: F401

    assert PREPARED_STATEMENT_OPERATIONS <= implemented_operations()


def test_create_prepared_statement_returns_empty(
    store: PreparedStatementStore,
) -> None:
    output = create_prepared_statement(
        store,
        {
            "StatementName": "flights_stmt",
            "WorkGroup": "analytics",
            "QueryStatement": "SELECT * FROM flights",
            "Description": "Flights query",
        },
    )

    assert output == {}
    record = store.get("flights_stmt", "analytics")
    assert record.statement_name == "flights_stmt"
    assert record.query_statement == "SELECT * FROM flights"
    assert record.description == "Flights query"
    assert record.workgroup == "analytics"


def test_create_prepared_statement_without_description(
    store: PreparedStatementStore,
) -> None:
    output = create_prepared_statement(
        store,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    assert output == {}
    record = store.get("test_stmt", "primary")
    assert record.description is None


def test_create_prepared_statement_duplicate_raises_invalid_request(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    with pytest.raises(
        InvalidRequestException, match="already exists in workgroup"
    ):
        create_prepared_statement(
            store,
            {
                "StatementName": "test_stmt",
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 2",
            },
        )


def test_create_prepared_statement_requires_statement_name(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="StatementName"):
        create_prepared_statement(
            store,
            {
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 1",
            },
        )


def test_create_prepared_statement_requires_workgroup(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        create_prepared_statement(
            store,
            {
                "StatementName": "test",
                "QueryStatement": "SELECT 1",
            },
        )


def test_create_prepared_statement_requires_query_statement(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryStatement"):
        create_prepared_statement(
            store,
            {
                "StatementName": "test",
                "WorkGroup": "primary",
            },
        )


def test_get_prepared_statement_returns_full_record(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "complex_stmt",
            "WorkGroup": "data_science",
            "QueryStatement": "SELECT a.* FROM a JOIN b ON a.id = b.id",
            "Description": "Complex join",
        },
    )

    output = get_prepared_statement(
        store, {"StatementName": "complex_stmt", "WorkGroup": "data_science"}
    )

    stmt = output["PreparedStatement"]
    assert stmt["StatementName"] == "complex_stmt"
    assert stmt["QueryStatement"] == "SELECT a.* FROM a JOIN b ON a.id = b.id"
    assert stmt["WorkGroupName"] == "data_science"
    assert stmt["Description"] == "Complex join"
    assert "LastModifiedTime" in stmt


def test_get_prepared_statement_missing_raises_resource_not_found(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        get_prepared_statement(
            store, {"StatementName": "missing-stmt", "WorkGroup": "primary"}
        )


def test_list_prepared_statements_returns_records_by_workgroup(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "stmt1",
            "WorkGroup": "analytics",
            "QueryStatement": "SELECT 1",
        },
    )
    create_prepared_statement(
        store,
        {
            "StatementName": "stmt2",
            "WorkGroup": "analytics",
            "QueryStatement": "SELECT 2",
        },
    )
    create_prepared_statement(
        store,
        {
            "StatementName": "stmt3",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 3",
        },
    )

    output = list_prepared_statements(store, {"WorkGroup": "analytics"})

    assert len(output["PreparedStatements"]) == 2
    assert "NextToken" not in output
    # ListPreparedStatements returns PreparedStatementSummary entries
    # (StatementName + LastModifiedTime only, per service-2.json shape).
    for item in output["PreparedStatements"]:
        assert set(item.keys()) == {"StatementName", "LastModifiedTime"}


def test_list_prepared_statements_empty_workgroup_returns_empty(
    store: PreparedStatementStore,
) -> None:
    output = list_prepared_statements(store, {"WorkGroup": "nonexistent"})

    assert output["PreparedStatements"] == []
    assert "NextToken" not in output


def test_list_prepared_statements_with_max_results(
    store: PreparedStatementStore,
) -> None:
    for i in range(5):
        create_prepared_statement(
            store,
            {
                "StatementName": f"stmt{i}",
                "WorkGroup": "analytics",
                "QueryStatement": f"SELECT {i}",
            },
        )

    output = list_prepared_statements(
        store, {"WorkGroup": "analytics", "MaxResults": 2}
    )

    assert len(output["PreparedStatements"]) == 2
    assert "NextToken" in output


def test_list_prepared_statements_pagination_round_trip(
    store: PreparedStatementStore,
) -> None:
    for i in range(5):
        create_prepared_statement(
            store,
            {
                "StatementName": f"stmt{i}",
                "WorkGroup": "analytics",
                "QueryStatement": f"SELECT {i}",
            },
        )

    page1 = list_prepared_statements(
        store, {"WorkGroup": "analytics", "MaxResults": 2}
    )
    assert len(page1["PreparedStatements"]) == 2
    assert "NextToken" in page1

    page2 = list_prepared_statements(
        store,
        {
            "WorkGroup": "analytics",
            "MaxResults": 2,
            "NextToken": page1["NextToken"],
        },
    )
    assert len(page2["PreparedStatements"]) == 2
    assert "NextToken" in page2

    page3 = list_prepared_statements(
        store,
        {
            "WorkGroup": "analytics",
            "MaxResults": 2,
            "NextToken": page2["NextToken"],
        },
    )
    assert len(page3["PreparedStatements"]) == 1
    assert "NextToken" not in page3


def test_list_prepared_statements_invalid_next_token_raises(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_prepared_statements(
            store, {"WorkGroup": "primary", "NextToken": "invalid"}
        )


def test_update_prepared_statement_modifies_record(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
            "Description": "Original",
        },
    )

    original_record = store.get("test_stmt", "primary")
    original_time = original_record.last_modified_time

    output = update_prepared_statement(
        store,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 2",
            "Description": "Updated",
        },
    )

    assert output == {}
    updated_record = store.get("test_stmt", "primary")
    assert updated_record.query_statement == "SELECT 2"
    assert updated_record.description == "Updated"
    assert updated_record.last_modified_time > original_time


def test_update_prepared_statement_missing_raises_resource_not_found(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        update_prepared_statement(
            store,
            {
                "StatementName": "missing-stmt",
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 1",
            },
        )


def test_delete_prepared_statement_removes_from_store(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "to_delete",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    output = delete_prepared_statement(
        store, {"StatementName": "to_delete", "WorkGroup": "primary"}
    )

    assert output == {}
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        store.get("to_delete", "primary")


def test_delete_prepared_statement_missing_raises_resource_not_found(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        delete_prepared_statement(
            store, {"StatementName": "missing-stmt", "WorkGroup": "primary"}
        )


def test_batch_get_prepared_statement_returns_found_records(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "stmt1",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )
    create_prepared_statement(
        store,
        {
            "StatementName": "stmt2",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 2",
        },
    )

    output = batch_get_prepared_statement(
        store,
        {"PreparedStatementNames": ["stmt1", "stmt2"], "WorkGroup": "primary"},
    )

    assert len(output["PreparedStatements"]) == 2
    assert "UnprocessedPreparedStatementNames" not in output
    names = {s["StatementName"] for s in output["PreparedStatements"]}
    assert names == {"stmt1", "stmt2"}


def test_batch_get_prepared_statement_unprocessed_missing_names(
    store: PreparedStatementStore,
) -> None:
    create_prepared_statement(
        store,
        {
            "StatementName": "stmt1",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    output = batch_get_prepared_statement(
        store,
        {
            "PreparedStatementNames": ["stmt1", "missing-1", "missing-2"],
            "WorkGroup": "primary",
        },
    )

    assert len(output["PreparedStatements"]) == 1
    assert output["PreparedStatements"][0]["StatementName"] == "stmt1"
    assert len(output["UnprocessedPreparedStatementNames"]) == 2
    # Missing names surface as UnprocessedPreparedStatementName structures
    # (StatementName member per service-2.json shape — never bare strings).
    unprocessed_names = {
        item["StatementName"]
        for item in output["UnprocessedPreparedStatementNames"]
    }
    assert unprocessed_names == {"missing-1", "missing-2"}


def test_batch_get_prepared_statement_requires_non_empty_list(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="must not be empty"):
        batch_get_prepared_statement(
            store, {"PreparedStatementNames": [], "WorkGroup": "primary"}
        )


def test_batch_get_prepared_statement_requires_list_of_strings(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(
        InvalidRequestException, match="must contain only strings"
    ):
        batch_get_prepared_statement(
            store, {"PreparedStatementNames": [123], "WorkGroup": "primary"}
        )
