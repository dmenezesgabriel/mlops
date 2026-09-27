"""Handler tests for the query-plane registry, read and
lifecycle operations.

Handlers translate a parsed JSON payload into the operation's output shape,
delegating lifecycle semantics to ``QueryExecutor`` (ADR-0009) and reads to
``ExecutionStore``. Records are created and transitioned directly through the
store so no Trino transport runs in unit tests; the executor's own lifecycle
is covered by the test_executor_* modules.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.common_schemas import (
    ResultConfiguration,
)
from athena_local.dispatch import implemented_operations
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    CANCELLED,
    QUEUED,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.main import reset_query_plane
from athena_local.query_executions import (
    batch_get_query_execution,
    get_query_execution,
    list_query_executions,
    register_query_execution_handlers,
    stop_query_execution,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore
from tests.unit._query_execution_fakes import (
    RecordingResultWriter,
    TerminalStatementClient,
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


QUERY_OPERATIONS = {
    "StartQueryExecution",
    "StopQueryExecution",
    "GetQueryExecution",
    "BatchGetQueryExecution",
    "GetQueryResults",
    "GetQueryRuntimeStatistics",
    "ListQueryExecutions",
}


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
        # main's composition root owns the six query ops once imported;
        # restore its wiring instead of popping them out of the registry.
        reset_query_plane()
        assert implemented_operations() == before


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


def test_list_returns_ids_newest_first(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    first = store.create(query="SELECT 1", workgroup="primary")
    second = store.create(query="SELECT 2", workgroup="primary")
    third = store.create(query="SELECT 3", workgroup="primary")

    output = list_query_executions(store, {})

    assert output["QueryExecutionIds"] == [
        third.query_execution_id,
        second.query_execution_id,
        first.query_execution_id,
    ]
    assert "NextToken" not in output


def test_list_defaults_to_primary_and_filters_workgroup(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    first = store.create(query="SELECT 1", workgroup="primary")
    second = store.create(query="SELECT 2", workgroup="primary")
    other = store.create(query="SELECT 3", workgroup="analytics")

    output = list_query_executions(store, {})

    assert output["QueryExecutionIds"] == [
        second.query_execution_id,
        first.query_execution_id,
    ]

    output = list_query_executions(store, {"WorkGroup": "analytics"})

    assert output["QueryExecutionIds"] == [other.query_execution_id]


def test_list_paginates_with_offset_next_token(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    records = [
        store.create(query=f"SELECT {index}", workgroup="primary")
        for index in range(5)
    ]

    first_page = list_query_executions(store, {"MaxResults": 2})

    assert first_page["QueryExecutionIds"] == [
        records[4].query_execution_id,
        records[3].query_execution_id,
    ]

    second_page = list_query_executions(
        store, {"MaxResults": 2, "NextToken": first_page["NextToken"]}
    )

    assert second_page["QueryExecutionIds"] == [
        records[2].query_execution_id,
        records[1].query_execution_id,
    ]

    third_page = list_query_executions(
        store, {"MaxResults": 2, "NextToken": second_page["NextToken"]}
    )

    assert third_page["QueryExecutionIds"] == [records[0].query_execution_id]
    assert "NextToken" not in third_page


def test_list_empty_store_returns_empty_ids(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    output = list_query_executions(store, {})

    assert output["QueryExecutionIds"] == []
    assert "NextToken" not in output


def test_list_rejects_non_int_max_results(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        list_query_executions(store, {"MaxResults": "10"})


def test_list_rejects_max_results_above_fifty(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="between 1 and 50"):
        list_query_executions(store, {"MaxResults": 51})


def test_list_rejects_invalid_next_token(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_query_executions(store, {"NextToken": "abc"})


def test_list_empty_body_defaults_to_primary(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    first = store.create(query="SELECT 1", workgroup="primary")

    output = list_query_executions(store, None)

    assert output["QueryExecutionIds"] == [first.query_execution_id]


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


def test_stop_on_terminal_execution_is_a_no_op(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    record = succeeded_result(store, [["1"]])

    output = asyncio.run(
        stop_query_execution(
            executor, {"QueryExecutionId": record.query_execution_id}
        )
    )

    # The model marks the op idempotent: a terminal execution answers 200
    # unchanged — the fake client's AssertionError proves no Trino DELETE ran.
    assert output == {}
    assert record.state == SUCCEEDED
