"""StartQueryExecution handler tests: EXECUTE resolution,
ClientRequestToken and ResultReuseConfiguration.

A missing prepared statement or parameter-count mismatch starts a FAILED
execution instead of a 400; a repeated token replays the original ID (changed
parameters reject); enabled reuse echoes the configuration and re-answers a
matching execution.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    FAILED,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.query_executions import (
    get_query_execution,
    start_query_execution,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore
from tests.unit._query_execution_fakes import (
    RecordingResultWriter,
    TerminalStatementClient,
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


def test_start_execute_resolves_and_submits_bound_statement(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create(
        "st", "SELECT 1 WHERE origin = ?", "primary", None
    )

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "EXECUTE \"st\" USING 'Washington'",
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
            prepared_statement_store=prepared_statements,
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        # The bound copy is submitted (record.resolved_statement) while the
        # wire Query keeps the submitted EXECUTE text.
        assert record.query == "EXECUTE \"st\" USING 'Washington'"
        assert record.resolved_statement == (
            "SELECT 1 WHERE origin = ('Washington')"
        )
        assert record.statement_type == "DML"
        assert record.substatement_type == "SELECT"
        assert record.workgroup == "primary"

    asyncio.run(scenario())


def test_start_execute_missing_statement_is_failed_execution(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    prepared_statements: PreparedStatementStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "EXECUTE nope",
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
            prepared_statement_store=prepared_statements,
        )

        record = store.get(output["QueryExecutionId"])
        # Real Athena fails the execution with its exact StateChangeReason;
        # the submitted text is the wire Query and the statement classifies
        # as UTILITY.
        assert record.state == FAILED
        assert record.state_change_reason == (
            "PreparedStatement nope was not found in workGroup primary"
        )
        assert record.query == "EXECUTE nope"
        assert record.statement_type == "UTILITY"
        assert record.resolved_statement is None
        assert record.query_execution_id not in executor._tasks

    asyncio.run(scenario())


def test_start_execute_count_mismatch_is_failed_execution(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    prepared_statements: PreparedStatementStore,
) -> None:
    prepared_statements.create("st", "SELECT ? AND ?", "primary", None)

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "EXECUTE st",
                "ExecutionParameters": ["1"],
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
            prepared_statement_store=prepared_statements,
        )

        record = store.get(output["QueryExecutionId"])
        assert record.state == FAILED
        assert record.state_change_reason == (
            "Incorrect number of parameters: expected 2 but found 1"
        )

    asyncio.run(scenario())


def test_start_execute_without_store_resolves_as_missing(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "EXECUTE st",
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        record = store.get(output["QueryExecutionId"])
        assert record.state == FAILED
        assert record.state_change_reason == (
            "PreparedStatement st was not found in workGroup primary"
        )

    asyncio.run(scenario())


CLIENT_TOKEN = "9f4b6c1a-2d3e-4f5a-8b7c-0d1e2f3a4b5c"  # IdempotencyToken max


def test_start_client_request_token_replays_the_original_id(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    """Idempotent retry (service-2.json): the same ClientRequestToken
    answers the original QueryExecutionId instead of a second execution."""

    async def scenario() -> None:
        payload = {
            "QueryString": "SELECT 1",
            "ClientRequestToken": CLIENT_TOKEN,
            "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
        }

        first = await start_query_execution(executor, workgroups, payload)
        second = await start_query_execution(executor, workgroups, payload)
        await executor._tasks[first["QueryExecutionId"]]

        assert second["QueryExecutionId"] == first["QueryExecutionId"]
        assert len(store.by_id) == 1

    asyncio.run(scenario())


def test_start_client_request_token_rejects_changed_parameters(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    """The model documents "an error is returned if a parameter, such as
    QueryString, has changed" for a previously seen ClientRequestToken."""

    async def scenario() -> None:
        await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "ClientRequestToken": CLIENT_TOKEN,
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        with pytest.raises(
            InvalidRequestException, match="ClientRequestToken"
        ):
            await start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 2",
                    "ClientRequestToken": CLIENT_TOKEN,
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )

    asyncio.run(scenario())


def test_start_rejects_non_string_client_request_token(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="ClientRequestToken"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "ClientRequestToken": 5,
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )


@pytest.mark.parametrize("token", ["", "x" * 37])
def test_start_rejects_client_request_token_out_of_model_bounds(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    token: str,
) -> None:
    # IdempotencyToken is bounded 1..36 (service-2.json); an empty token
    # must never dedupe distinct submissions against each other.
    with pytest.raises(InvalidRequestException, match="ClientRequestToken"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "ClientRequestToken": token,
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )


REUSE_PAYLOAD = {
    "ResultReuseByAgeConfiguration": {"Enabled": True, "MaxAgeInMinutes": 30}
}


def test_start_parses_and_echoes_result_reuse_configuration(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    """GetQueryExecution reports the reuse behavior that was used
    (service-2.json QueryExecution.ResultReuseConfiguration)."""

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q/"},
                "ResultReuseConfiguration": REUSE_PAYLOAD,
            },
        )
        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]

        execution = get_query_execution(
            store, {"QueryExecutionId": output["QueryExecutionId"]}
        )["QueryExecution"]
        assert execution["ResultReuseConfiguration"] == REUSE_PAYLOAD
        assert execution["Statistics"]["ResultReuseInformation"] == {
            "ReusedPreviousResult": False
        }

    asyncio.run(scenario())


def test_start_rejects_invalid_result_reuse_configuration(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    # Enabled is the required member of ResultReuseByAgeConfiguration
    # (service-2.json).
    with pytest.raises(InvalidRequestException, match="Enabled"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q/"
                    },
                    "ResultReuseConfiguration": {
                        "ResultReuseByAgeConfiguration": {}
                    },
                },
            )
        )


def test_start_result_reuse_reanswers_the_previous_execution(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    """A second identical enabled submission reports ReusedPreviousResult
    and the source's OutputLocation without a new Trino round-trip."""

    async def scenario() -> None:
        request = {
            "QueryString": "SELECT 1",
            "ResultConfiguration": {"OutputLocation": "s3://bucket/q/"},
            "ResultReuseConfiguration": REUSE_PAYLOAD,
        }
        first_id = (
            await start_query_execution(executor, workgroups, request)
        )["QueryExecutionId"]
        await executor._tasks[first_id]

        second_id = (
            await start_query_execution(executor, workgroups, request)
        )["QueryExecutionId"]

        assert second_id != first_id
        first_execution = get_query_execution(
            store, {"QueryExecutionId": first_id}
        )["QueryExecution"]
        second_execution = get_query_execution(
            store, {"QueryExecutionId": second_id}
        )["QueryExecution"]
        assert second_execution["Status"]["State"] == SUCCEEDED
        assert second_execution["Statistics"]["ResultReuseInformation"] == {
            "ReusedPreviousResult": True
        }
        assert (
            second_execution["ResultConfiguration"]["OutputLocation"]
            == first_execution["ResultConfiguration"]["OutputLocation"]
        )

    asyncio.run(scenario())


def test_start_client_request_token_rejects_changed_reuse_configuration(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    """ResultReuseConfiguration is a request parameter like any other: a
    retried token carrying a different one errors (model idempotent rule)."""

    async def scenario() -> None:
        await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "ClientRequestToken": CLIENT_TOKEN,
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )
        with pytest.raises(InvalidRequestException, match=CLIENT_TOKEN):
            await start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "ClientRequestToken": CLIENT_TOKEN,
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                    "ResultReuseConfiguration": REUSE_PAYLOAD,
                },
            )

    asyncio.run(scenario())
