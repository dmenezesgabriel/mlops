"""GetQueryResults / GetQueryRuntimeStatistics handler
tests.

Inline rows answer from the page the executor stashed before SUCCEEDED
(ADR-0007 #4): the header row rides page zero only when the execution
carried result columns, ``MaxResults``/``NextToken`` slice data-row offsets,
and a zero-column result (DDL, FAILED) answers an empty ``Rows`` — real AWS
emits no header without columns and consumers like the terraform provider's
``executeAndExpectNoRows`` require it.
"""

from __future__ import annotations

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    FAILED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.query_results import (
    get_query_results,
    get_query_runtime_statistics,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore
from tests.unit._query_execution_fakes import (
    RecordingResultWriter,
    TerminalStatementClient,
    page_values,
    succeeded_result,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


@pytest.fixture()
def executor(store: ExecutionStore) -> QueryExecutor:
    return QueryExecutor(
        store=store,
        client=TerminalStatementClient(),
        writer=RecordingResultWriter(),
    )


@pytest.fixture()
def workgroups() -> WorkGroupStore:
    return WorkGroupStore()


@pytest.fixture()
def prepared_statements() -> PreparedStatementStore:
    return PreparedStatementStore()


def test_get_results_pre_finish_is_shaped_400(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)

    with pytest.raises(InvalidRequestException) as error:
        get_query_results(
            store, executor, {"QueryExecutionId": record.query_execution_id}
        )

    assert "Current state: RUNNING" in str(error.value)


def test_get_results_succeeded_returns_header_and_rows(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)
    record.cache_result_page(
        [("col_a", "varchar"), ("col_b", "integer")], [["x", 3]]
    )
    record.transition_to(SUCCEEDED)

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    result_set = output["ResultSet"]
    assert result_set["ResultSetMetadata"] == {
        "ColumnInfo": [
            {"Name": "col_a", "Type": "varchar"},
            {"Name": "col_b", "Type": "integer"},
        ]
    }
    assert result_set["Rows"] == [
        {
            "Data": [
                {"VarCharValue": "col_a"},
                {"VarCharValue": "col_b"},
            ]
        },
        {
            "Data": [
                {"VarCharValue": "x"},
                {"VarCharValue": "3"},
            ]
        },
    ]


def test_get_results_serializes_cell_types_to_varchar_value(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(
        store,
        [
            [
                3,
                1.5,
                True,
                False,
                "12.34",
                "2023-06-15",
                "2023-06-15 10:20:30.123",
            ]
        ],
        columns=[
            ("n", "integer"),
            ("d", "double"),
            ("t", "boolean"),
            ("f", "boolean"),
            ("dec", "decimal(6,2)"),
            ("dt", "date"),
            ("ts", "timestamp"),
        ],
    )

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    # Numbers, decimals, dates and timestamps travel as plain strings while
    # booleans use Athena's lowercase wire form rather than Python's str().
    assert output["ResultSet"]["Rows"][1]["Data"] == [
        {"VarCharValue": "3"},
        {"VarCharValue": "1.5"},
        {"VarCharValue": "true"},
        {"VarCharValue": "false"},
        {"VarCharValue": "12.34"},
        {"VarCharValue": "2023-06-15"},
        {"VarCharValue": "2023-06-15 10:20:30.123"},
    ]


def test_get_results_null_cells_omit_varchar_value_key(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(
        store,
        [[None], ["x"]],
        columns=[("a", "varchar")],
    )

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    # The service model makes Datum.VarCharValue optional, so a null cell
    # must be an empty datum rather than {"VarCharValue": ""}.
    assert output["ResultSet"]["Rows"][1]["Data"] == [{}]
    assert output["ResultSet"]["Rows"][2]["Data"] == [{"VarCharValue": "x"}]


def test_get_results_failed_execution_returns_empty_result_set(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(query="SELEC", workgroup="primary")
    record.transition_to(RUNNING)
    record.transition_to(FAILED, reason="syntax error")

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    assert output["ResultSet"]["Rows"] == []
    assert output["ResultSet"]["ResultSetMetadata"]["ColumnInfo"] == []


def test_get_results_zero_column_result_set_has_no_header_row(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    # terraform-provider-aws's executeAndExpectNoRows hard-fails on ANY row
    # for DDL (internal/service/athena/database.go); real AWS answers
    # Rows: [] when the execution carried no result columns.
    record = store.create(query="CREATE SCHEMA x", workgroup="primary")
    record.transition_to(RUNNING)
    record.cache_result_page([], [])
    record.transition_to(SUCCEEDED)

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    assert output["ResultSet"]["Rows"] == []
    assert output["ResultSet"]["ResultSetMetadata"]["ColumnInfo"] == []


def test_get_results_unknown_execution_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_query_results(store, executor, {"QueryExecutionId": "missing"})


def test_get_results_paginates_with_header_only_on_first_page(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(store, [[str(n)] for n in range(1, 6)])

    first = get_query_results(
        store,
        executor,
        {
            "QueryExecutionId": record.query_execution_id,
            "MaxResults": 2,
        },
    )

    # The header row travels only on page zero (wrangler strips it with
    # page_rows[1:] on the first page only — _read.py:357).
    assert [page_values(row) for row in first["ResultSet"]["Rows"]] == [
        ["id"],
        ["1"],
        ["2"],
    ]
    assert first["NextToken"] == "2"

    second = get_query_results(
        store,
        executor,
        {
            "QueryExecutionId": record.query_execution_id,
            "MaxResults": 2,
            "NextToken": first["NextToken"],
        },
    )
    assert [page_values(row) for row in second["ResultSet"]["Rows"]] == [
        ["3"],
        ["4"],
    ]
    assert second["NextToken"] == "4"

    third = get_query_results(
        store,
        executor,
        {
            "QueryExecutionId": record.query_execution_id,
            "MaxResults": 2,
            "NextToken": second["NextToken"],
        },
    )
    assert [page_values(row) for row in third["ResultSet"]["Rows"]] == [["5"]]
    assert "NextToken" not in third


def test_get_results_single_page_when_all_rows_fit(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(store, [["1"], ["2"]])

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    assert output["ResultSet"]["ResultSetMetadata"] == {
        "ColumnInfo": [{"Name": "id", "Type": "integer"}]
    }
    assert [page_values(row) for row in output["ResultSet"]["Rows"]] == [
        ["id"],
        ["1"],
        ["2"],
    ]
    assert "NextToken" not in output


def test_get_results_default_max_results_is_1000(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(store, [[str(n)] for n in range(1, 1002)])

    first = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    # 1000 data rows beside the header; the 1001st needs a follow-up page.
    assert len(first["ResultSet"]["Rows"]) == 1001
    assert first["NextToken"] == "1000"

    last = get_query_results(
        store,
        executor,
        {
            "QueryExecutionId": record.query_execution_id,
            "NextToken": first["NextToken"],
        },
    )
    assert [page_values(row) for row in last["ResultSet"]["Rows"]] == [
        ["1001"]
    ]
    assert "NextToken" not in last


@pytest.mark.parametrize("max_results", [0, -3, 1001])
def test_get_results_max_results_out_of_range_is_shaped_400(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    max_results: int,
) -> None:
    record = succeeded_result(store, [["1"]])

    with pytest.raises(InvalidRequestException) as error:
        get_query_results(
            store,
            executor,
            {
                "QueryExecutionId": record.query_execution_id,
                "MaxResults": max_results,
            },
        )

    assert "between 1 and 1000" in str(error.value)
    assert str(max_results) in str(error.value)


@pytest.mark.parametrize("next_token", ["", "abc", "12abc", "-1", "1.5"])
def test_get_results_invalid_next_token_is_shaped_400(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    next_token: str,
) -> None:
    record = succeeded_result(store, [["1"]])

    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        get_query_results(
            store,
            executor,
            {
                "QueryExecutionId": record.query_execution_id,
                "NextToken": next_token,
            },
        )


def test_get_results_next_token_past_end_returns_no_rows(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(store, [["1"]])

    output = get_query_results(
        store,
        executor,
        {
            "QueryExecutionId": record.query_execution_id,
            "NextToken": "1",
        },
    )

    # Offset past the last data row: no header (page zero only), no rows,
    # and no token because nothing remains.
    assert output["ResultSet"]["Rows"] == []
    assert "NextToken" not in output


def test_runtime_statistics_return_recorded_counters(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.apply_engine_statistics(
        {"processedBytes": 1024, "wallTimeMillis": 250}
    )

    output = get_query_runtime_statistics(
        store, {"QueryExecutionId": record.query_execution_id}
    )

    statistics = output["QueryRuntimeStatistics"]
    assert statistics["Timeline"] == {"EngineExecutionTimeInMillis": 250}
    assert statistics["Rows"] == {"InputBytes": 1024}


def test_runtime_statistics_unknown_execution_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_query_runtime_statistics(store, {"QueryExecutionId": "missing"})
