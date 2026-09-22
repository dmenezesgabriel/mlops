"""Handler tests for the six query-plane operations (QE-3).

Handlers translate a parsed JSON payload into the operation's output shape,
delegating lifecycle semantics to ``QueryExecutor`` (ADR-0009) and reads to
``ExecutionStore``. Records are created and transitioned directly through the
store so no Trino transport runs in unit tests; the executor's own lifecycle
is already covered in test_executor.py. GetQueryResults inline rows come from
the page the executor stashed before SUCCEEDED (ADR-0007 #4), and the failed
path returns a header-only result set (moto never raises on state at
``moto/athena/models.py:415``; wrangler only reads inline results for
SUCCEEDED executions).
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.common_schemas import ResultConfiguration
from athena_local.dispatch import OPERATION_HANDLERS, implemented_operations
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    CANCELLED,
    FAILED,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.executor import QueryExecutor
from athena_local.query_executions import (
    batch_get_query_execution,
    get_query_execution,
    get_query_results,
    get_query_runtime_statistics,
    register_query_execution_handlers,
    start_query_execution,
    stop_query_execution,
)
from athena_local.state import WorkGroupStore
from athena_local.trino_client import TrinoColumn, TrinoPage
from athena_local.workgroup_schemas import WorkGroupConfiguration

QUERY_OPERATIONS = {
    "StartQueryExecution",
    "StopQueryExecution",
    "GetQueryExecution",
    "BatchGetQueryExecution",
    "GetQueryResults",
    "GetQueryRuntimeStatistics",
}


def _terminal_page() -> TrinoPage:
    """A single FINISHED page so started executions complete immediately."""
    return TrinoPage(
        query_id="q",
        next_uri=None,
        update_type=None,
        columns=[TrinoColumn(name="col", column_type="varchar")],
        data=[["ok"]],
        stats={"state": "FINISHED", "processedBytes": 64, "wallTimeMillis": 5},
        error=None,
    )


class TerminalStatementClient:
    """StatementClient fake serving one terminal page and recording nothing."""

    async def submit_statement(
        self, query: str, catalog: str, schema: str, user: str
    ) -> TrinoPage:
        return _terminal_page()

    async def fetch_next(self, next_uri: str) -> None:
        raise AssertionError("single-page submissions never poll Trino")

    async def cancel(self, next_uri: str) -> None:
        raise AssertionError("handler tests never cancel Trino")


class RecordingResultWriter:
    """ResultArtifactWriter fake recording every persisted execution."""

    def __init__(self) -> None:
        self.writes: list[tuple[object, TrinoPage]] = []

    async def write(self, execution: object, final_page: TrinoPage) -> None:
        self.writes.append((execution, final_page))


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


def test_query_operations_register_against_the_registry(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    before = implemented_operations()
    register_query_execution_handlers(store, executor, workgroups)
    try:
        assert QUERY_OPERATIONS <= implemented_operations()
    finally:
        for operation in QUERY_OPERATIONS:
            OPERATION_HANDLERS.pop(operation, None)
        assert implemented_operations() == before


def test_start_returns_id_and_stores_request(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "QueryExecutionContext": {"Database": "analytics"},
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert output["QueryExecutionId"] == record.query_execution_id
        assert record.query == "SELECT 1"
        assert record.workgroup == "primary"
        assert record.database == "analytics"
        assert record.result_configuration == ResultConfiguration(
            output_location="s3://bucket/q.csv"
        )

    asyncio.run(scenario())


def test_start_defaults_to_primary_workgroup(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.workgroup == "primary"

    asyncio.run(scenario())


def test_get_query_execution_reports_classified_statement_types(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    async def scenario() -> None:
        select_id = (
            await start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "-- question\nSELECT 1",
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )["QueryExecutionId"]
        ctas_id = (
            await start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": (
                        "CREATE TABLE db.t WITH (external_location = 's3://b/k') "
                        "AS SELECT 1"
                    ),
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )["QueryExecutionId"]
        await executor._tasks[select_id]
        await executor._tasks[ctas_id]

        select_payload = get_query_execution(
            store, {"QueryExecutionId": select_id}
        )["QueryExecution"]
        ctas_payload = get_query_execution(
            store, {"QueryExecutionId": ctas_id}
        )["QueryExecution"]

        assert select_payload["StatementType"] == "DML"
        assert select_payload["SubstatementType"] == "SELECT"
        assert ctas_payload["StatementType"] == "DDL"
        assert ctas_payload["SubstatementType"] == "CREATE_TABLE_AS_SELECT"

    asyncio.run(scenario())


def test_start_falls_back_to_workgroup_output_location(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    workgroups.create(
        "analytics",
        WorkGroupConfiguration(
            result_configuration=ResultConfiguration(
                output_location="s3://wg-bucket/out/"
            )
        ),
        None,
        [],
    )

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {"QueryString": "SELECT 1", "WorkGroup": "analytics"},
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.result_configuration == ResultConfiguration(
            output_location="s3://wg-bucket/out/"
        )

    asyncio.run(scenario())


def test_start_enforced_workgroup_wins_over_request_location(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    workgroups.create(
        "enforced",
        WorkGroupConfiguration(
            result_configuration=ResultConfiguration(
                output_location="s3://wg/forced/"
            ),
            enforce_work_group_configuration=True,
        ),
        None,
        [],
    )

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "WorkGroup": "enforced",
                "ResultConfiguration": {
                    "OutputLocation": "s3://bucket/request.csv"
                },
            },
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.result_configuration == ResultConfiguration(
            output_location="s3://wg/forced/"
        )

    asyncio.run(scenario())


def test_start_unknown_workgroup_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {"QueryString": "SELECT 1", "WorkGroup": "nope"},
            )
        )


def test_start_requires_query_string(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryString"):
        asyncio.run(start_query_execution(executor, workgroups, {}))


def test_start_without_any_output_location_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="OutputLocation"):
        asyncio.run(
            start_query_execution(
                executor, workgroups, {"QueryString": "SELECT 1"}
            )
        )


def test_start_rejects_non_object_query_execution_context(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryExecutionContext"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "QueryExecutionContext": "analytics",
                },
            )
        )


def test_start_rejects_non_string_database_member(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Database"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "QueryExecutionContext": {"Database": 5},
                },
            )
        )


def test_start_rejects_non_list_execution_parameters(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="ExecutionParameters"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT ?",
                    "ExecutionParameters": "1",
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )


def test_start_rejects_non_string_parameter_member(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="ExecutionParameters"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT ?",
                    "ExecutionParameters": ["1", 3],
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )


def test_start_passes_execution_parameters(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT ?",
                "ExecutionParameters": ["1"],
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.execution_parameters == ["1"]

    asyncio.run(scenario())


def test_get_returns_full_payload(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    output = get_query_execution(
        store, {"QueryExecutionId": record.query_execution_id}
    )

    assert output["QueryExecution"]["QueryExecutionId"] == (
        record.query_execution_id
    )
    assert output["QueryExecution"]["Query"] == "SELECT 1"
    assert output["QueryExecution"]["Status"]["State"] == QUEUED


def test_get_query_execution_reports_full_artifact_path(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(
        query="SELECT 1",
        workgroup="primary",
        result_configuration=ResultConfiguration(
            output_location="s3://results-bucket/analytics/"
        ),
        statement_type="DML",
        substatement_type="SELECT",
    )

    output = get_query_execution(
        store, {"QueryExecutionId": record.query_execution_id}
    )

    assert output["QueryExecution"]["ResultConfiguration"][
        "OutputLocation"
    ] == (f"s3://results-bucket/analytics/{record.query_execution_id}.csv")


def test_get_none_payload_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryExecutionId"):
        get_query_execution(store, None)


def test_get_rejects_malformed_query_execution_id(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryExecutionId"):
        get_query_execution(store, {"QueryExecutionId": 7})


def test_get_unknown_execution_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_query_execution(store, {"QueryExecutionId": "missing"})


def test_batch_get_returns_found_and_unprocessed(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    first = store.create(query="SELECT 1", workgroup="primary")
    second = store.create(query="SELECT 2", workgroup="primary")

    output = batch_get_query_execution(
        store,
        {
            "QueryExecutionIds": [
                first.query_execution_id,
                "missing",
                second.query_execution_id,
            ]
        },
    )

    assert [
        item["QueryExecutionId"] for item in output["QueryExecutions"]
    ] == [
        first.query_execution_id,
        second.query_execution_id,
    ]
    assert output["UnprocessedQueryExecutionIds"] == [
        {
            "QueryExecutionId": "missing",
            "ErrorCode": "InvalidRequestException",
            "ErrorMessage": "QueryExecution missing does not exist",
        }
    ]


def test_batch_get_rejects_non_list_ids(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryExecutionIds"):
        batch_get_query_execution(store, {"QueryExecutionIds": "abc"})


def test_batch_get_rejects_empty_ids(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryExecutionIds"):
        batch_get_query_execution(store, {"QueryExecutionIds": []})


def test_batch_get_rejects_non_string_ids(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryExecutionIds"):
        batch_get_query_execution(store, {"QueryExecutionIds": [123]})


def test_stop_marks_execution_cancelled(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = store.create(query="SELECT 1", workgroup="primary")

    output = asyncio.run(
        stop_query_execution(
            executor, {"QueryExecutionId": record.query_execution_id}
        )
    )

    assert output == {}
    assert record.state == CANCELLED


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

    assert output["ResultSet"]["Rows"] == [{"Data": []}]
    assert output["ResultSet"]["ResultSetMetadata"]["ColumnInfo"] == []


def test_get_results_unknown_execution_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_query_results(store, executor, {"QueryExecutionId": "missing"})


def _succeeded_result(
    store: ExecutionStore,
    rows: list[list[object]],
    columns: list[tuple[str, str]] | None = None,
) -> QueryExecutionRecord:
    record = store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)
    record.cache_result_page(
        columns or [("id", "integer")],
        rows,
    )
    record.transition_to(SUCCEEDED)
    return record


def _page_values(row: dict[str, object]) -> list[str]:
    """Strip a wire Row down to its VarCharValue cell strings."""
    data = row["Data"]
    assert isinstance(data, list)
    return [
        cell["VarCharValue"]
        for cell in data
        if isinstance(cell, dict) and "VarCharValue" in cell
    ]


def test_get_results_paginates_with_header_only_on_first_page(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = _succeeded_result(store, [[str(n)] for n in range(1, 6)])

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
    assert [_page_values(row) for row in first["ResultSet"]["Rows"]] == [
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
    assert [_page_values(row) for row in second["ResultSet"]["Rows"]] == [
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
    assert [_page_values(row) for row in third["ResultSet"]["Rows"]] == [["5"]]
    assert "NextToken" not in third


def test_get_results_single_page_when_all_rows_fit(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = _succeeded_result(store, [["1"], ["2"]])

    output = get_query_results(
        store, executor, {"QueryExecutionId": record.query_execution_id}
    )

    assert output["ResultSet"]["ResultSetMetadata"] == {
        "ColumnInfo": [{"Name": "id", "Type": "integer"}]
    }
    assert [_page_values(row) for row in output["ResultSet"]["Rows"]] == [
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
    record = _succeeded_result(store, [[str(n)] for n in range(1, 1002)])

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
    assert [_page_values(row) for row in last["ResultSet"]["Rows"]] == [
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
    record = _succeeded_result(store, [["1"]])

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
    record = _succeeded_result(store, [["1"]])

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
    record = _succeeded_result(store, [["1"]])

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
