"""Idempotent replay and result reuse in the submit path.

A repeated ClientRequestToken re-answers the original execution (changed
parameters reject instead), scoped per workgroup; ResultReuseConfiguration
re-answers a recent identical SELECT and runs fresh otherwise.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.common_schemas import (
    ResultConfiguration,
    ResultReuseByAgeConfiguration,
)
from athena_local.errors import (
    InvalidRequestException,
)
from athena_local.executions import (
    FAILED,
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.statement_classification import StatementClassification
from athena_local.trino_client import (
    TrinoColumn,
)
from tests.unit._executor_fakes import (
    RecordingWriter,
    ScriptedStatementClient,
    result_page,
)


@pytest.fixture()
def store() -> ExecutionStore:
    return ExecutionStore()


def test_client_request_token_replays_the_original_execution(
    store: ExecutionStore,
) -> None:
    """StartQueryExecution is idempotent (service-2.json): a retried
    ClientRequestToken answers the original record and never reaches Trino."""

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        first = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            client_request_token="token-1",
        )
        await executor._tasks[first.query_execution_id]

        replayed = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            client_request_token="token-1",
        )

        assert replayed is first
        # No second submit/preflight — the retry never touched Trino.
        assert len(client.submissions) == 1

    asyncio.run(scenario())


def test_client_request_token_rejects_a_changed_request(
    store: ExecutionStore,
) -> None:
    """The model errors when a previous token arrives with changed
    parameters ("a parameter, such as QueryString, has changed")."""

    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        await executor.start(
            query="SELECT 1",
            workgroup="primary",
            client_request_token="token-1",
        )

        with pytest.raises(InvalidRequestException, match="token-1"):
            await executor.start(
                query="SELECT 2",
                workgroup="primary",
                client_request_token="token-1",
            )

    asyncio.run(scenario())


def test_client_request_token_scopes_to_the_workgroup(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=None), result_page(next_uri=None)]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        first = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            client_request_token="token-1",
        )
        second = await executor.start(
            query="SELECT 1",
            workgroup="analytics",
            client_request_token="token-1",
        )
        await executor._tasks[first.query_execution_id]
        await executor._tasks[second.query_execution_id]

        assert second is not first
        assert len(client.submissions) == 2

    asyncio.run(scenario())


def test_client_request_token_replays_a_failed_resolution(
    store: ExecutionStore,
) -> None:
    """A retried EXECUTE that failed statement resolution replays the same
    FAILED record — the request was already accepted, so idempotent replay
    answers the original id."""

    async def scenario() -> None:
        client = ScriptedStatementClient([])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        reason = "PreparedStatement st does not exist in workgroup primary"
        first = await executor.start(
            query='EXECUTE "st"',
            workgroup="primary",
            client_request_token="token-1",
            resolution_failure_reason=reason,
        )

        replayed = await executor.start(
            query='EXECUTE "st"',
            workgroup="primary",
            client_request_token="token-1",
            resolution_failure_reason=reason,
        )

        assert replayed is first
        assert replayed.state == FAILED
        assert client.submissions == []

    asyncio.run(scenario())


def test_requests_without_token_get_distinct_executions(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=None), result_page(next_uri=None)]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        first = await executor.start(query="SELECT 1", workgroup="primary")
        second = await executor.start(query="SELECT 1", workgroup="primary")
        await executor._tasks[first.query_execution_id]
        await executor._tasks[second.query_execution_id]

        assert second.query_execution_id != first.query_execution_id

    asyncio.run(scenario())


ENABLED_REUSE = ResultReuseByAgeConfiguration(
    enabled=True, max_age_in_minutes=60
)
SELECT_CLASSIFICATION = StatementClassification(
    statement_type="DML", substatement_type="SELECT"
)
RESULT_PREFIX = ResultConfiguration(output_location="s3://bucket/results/")


def test_result_reuse_reanswers_a_recent_identical_execution(
    store: ExecutionStore,
) -> None:
    """With Enabled, a second identical submission bypasses Trino entirely
    and answers the previous result (UG "Reusing query results")."""

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(
                    next_uri=None,
                    columns=[TrinoColumn(name="col", column_type="integer")],
                    data=[[7]],
                )
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        first = await executor.start(
            query="SELECT 7",
            workgroup="primary",
            result_configuration=RESULT_PREFIX,
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[first.query_execution_id]

        second = await executor.start(
            query="SELECT 7",
            workgroup="primary",
            result_configuration=RESULT_PREFIX,
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=SELECT_CLASSIFICATION,
        )

        assert second is not first
        assert second.state == SUCCEEDED
        assert second.reused_previous_result is True
        # The reused result copies the cached page and reports the source's
        # artifact path — no second submit, no second result file.
        assert second.result_rows == [[7]]
        assert (
            second._result_output_location() == first._result_output_location()
        )
        assert len(client.submissions) == 1
        assert second.query_execution_id not in executor._tasks

    asyncio.run(scenario())


def test_result_reuse_runs_fresh_when_disabled(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=None), result_page(next_uri=None)]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        disabled = ResultReuseByAgeConfiguration(enabled=False)
        first = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=disabled,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[first.query_execution_id]

        second = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=disabled,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[second.query_execution_id]

        assert second.reused_previous_result is False
        assert len(client.submissions) == 2

    asyncio.run(scenario())


def test_result_reuse_ignores_results_older_than_max_age(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient(
            [result_page(next_uri=None), result_page(next_uri=None)]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        first = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[first.query_execution_id]
        assert first.completion_time is not None
        first.completion_time -= 120

        second = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=ResultReuseByAgeConfiguration(
                enabled=True, max_age_in_minutes=1
            ),
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[second.query_execution_id]

        assert second.reused_previous_result is False
        assert len(client.submissions) == 2

    asyncio.run(scenario())


def test_result_reuse_skips_non_select_and_managed_submissions(
    store: ExecutionStore,
) -> None:
    """Only SELECT/EXECUTE produce reusable result sets, and managed-results
    workgroups are excluded — both run fresh (UG "Reusing query results")."""

    async def scenario() -> None:
        client = ScriptedStatementClient(
            [
                result_page(next_uri=None),
                result_page(next_uri=None),
                result_page(next_uri=None),
            ]
        )
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        source = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[source.query_execution_id]

        insert = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=StatementClassification(
                statement_type="DML", substatement_type="INSERT"
            ),
        )
        await executor._tasks[insert.query_execution_id]
        managed = await executor.start(
            query="SELECT 1",
            workgroup="managed",
            managed_results=True,
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[managed.query_execution_id]

        assert insert.reused_previous_result is False
        assert managed.reused_previous_result is False
        assert len(client.submissions) == 3

    asyncio.run(scenario())


def test_result_reuse_reports_no_reuse_without_a_prior_match(
    store: ExecutionStore,
) -> None:
    async def scenario() -> None:
        client = ScriptedStatementClient([result_page(next_uri=None)])
        executor = QueryExecutor(
            store=store, client=client, writer=RecordingWriter()
        )
        record = await executor.start(
            query="SELECT 1",
            workgroup="primary",
            result_reuse_configuration=ENABLED_REUSE,
            statement_classification=SELECT_CLASSIFICATION,
        )
        await executor._tasks[record.query_execution_id]

        assert record.state == SUCCEEDED
        assert record.reused_previous_result is False
        assert len(client.submissions) == 1

    asyncio.run(scenario())
