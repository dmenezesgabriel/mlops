"""ListPreparedStatements / BatchGetPreparedStatement handler tests.

Both ops return collections: the list paginates per-workgroup with an opaque
offset ``NextToken``, and batch_get splits found records from unprocessed
names per the model's output shape.
"""

from __future__ import annotations

import pytest
from athena_local.errors import (
    InvalidRequestException,
)
from athena_local.prepared_statements import (
    create_prepared_statement,
    list_prepared_statements,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore


@pytest.fixture()
def store() -> PreparedStatementStore:
    return PreparedStatementStore()


@pytest.fixture()
def workgroups() -> WorkGroupStore:
    return WorkGroupStore()


def test_list_prepared_statements_returns_records_by_workgroup(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "stmt1",
            "WorkGroup": "analytics",
            "QueryStatement": "SELECT 1",
        },
    )
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "stmt2",
            "WorkGroup": "analytics",
            "QueryStatement": "SELECT 2",
        },
    )
    create_prepared_statement(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    output = list_prepared_statements(store, {"WorkGroup": "nonexistent"})

    assert output["PreparedStatements"] == []
    assert "NextToken" not in output


def test_list_prepared_statements_with_max_results(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    for i in range(5):
        create_prepared_statement(
            store,
            workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    for i in range(5):
        create_prepared_statement(
            store,
            workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_prepared_statements(
            store, {"WorkGroup": "primary", "NextToken": "invalid"}
        )
