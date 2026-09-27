"""StartQueryExecution handler tests: submission and
validation.

Statement classification reporting, Database-context unquoting, workgroup
defaults and enabled checks, the QueryString model bound, workgroup output
location resolution (enforced wins, fallback, managed workgroups) and the
required-OutputLocation 400.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.common_schemas import (
    ManagedQueryResultsConfiguration,
    ResultConfiguration,
)
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.query_executions import (
    get_query_execution,
    start_query_execution,
)
from athena_local.query_results import (
    get_query_results,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore
from athena_local.workgroup_schemas import WorkGroupConfiguration
from tests.unit._query_execution_fakes import (
    RecordingResultWriter,
    TerminalStatementClient,
    page_value_names,
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


def test_start_unquotes_quoted_database_context(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    """awswrangler backticks the context Database (athena/_utils.py:660-661)."""

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "QueryExecutionContext": {"Database": "`analytics`"},
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.database == "analytics"

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


def test_start_rejects_query_string_over_model_maximum(
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    # Canonical-model QueryString is bounded at 262144 characters
    # (service-2.json); a longer statement 400s at submit, like real Athena.
    oversized = "SELECT " + "x" * 262144
    with pytest.raises(InvalidRequestException, match="262144"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": oversized,
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
            )
        )


def test_start_accepts_query_string_at_model_maximum(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT " + "x" * 262137,  # exactly 262144
                "ResultConfiguration": {"OutputLocation": "s3://bucket/q.csv"},
            },
        )

        await executor._tasks[output["QueryExecutionId"]]
        assert store.get(output["QueryExecutionId"]).state == SUCCEEDED

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


def test_start_disabled_workgroup_is_shaped_error(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    workgroups.create(
        "blocked", WorkGroupConfiguration(), description=None, tags=[]
    )
    workgroups.update(
        "blocked", description=None, state="DISABLED", updates=None
    )

    with pytest.raises(
        InvalidRequestException, match="WorkGroup blocked is disabled"
    ):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "WorkGroup": "blocked",
                    "ResultConfiguration": {"OutputLocation": "s3://b/"},
                },
            )
        )
    assert store.by_id == {}  # rejected before any execution was queued


def test_start_requires_query_string(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryString"):
        asyncio.run(start_query_execution(executor, workgroups, {}))


def _create_managed_workgroup(
    workgroups: WorkGroupStore, name: str = "managed"
) -> None:
    """Seed a workgroup whose ManagedQueryResultsConfiguration.Enabled is true.

    The canonical service model forbids ``ResultConfiguration.OutputLocation``
    on such a workgroup ("A workgroup cannot have the ResultConfiguration$
    OutputLocation parameter"), so it carries no ResultConfiguration — exactly
    the shape awswrangler's ``workgroup_managed`` fixture uses
    (awswrangler/tests/conftest.py:147-156).
    """
    workgroups.create(
        name,
        WorkGroupConfiguration(
            managed_query_results_configuration=ManagedQueryResultsConfiguration(
                enabled=True
            )
        ),
        None,
        [],
    )


def test_start_managed_workgroup_accepts_no_output_location(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    _create_managed_workgroup(workgroups)

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {"QueryString": "SELECT 1", "WorkGroup": "managed"},
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.state == SUCCEEDED
        # Managed executions store an empty ResultConfiguration so the wire
        # still reports the member while carrying no OutputLocation (the
        # shape wrangler's managed read asserts on), and the writer is
        # skipped (ADR-0011) so this succeeds with nothing on S3.
        assert record.result_configuration == ResultConfiguration()
        payload = get_query_execution(
            store, {"QueryExecutionId": output["QueryExecutionId"]}
        )["QueryExecution"]
        assert "ResultConfiguration" in payload
        assert "OutputLocation" not in payload["ResultConfiguration"]
        # Inline GetQueryResults still serves the cached terminal rows.
        result_set = get_query_results(
            store, executor, {"QueryExecutionId": output["QueryExecutionId"]}
        )["ResultSet"]
        assert page_value_names(result_set) == [["col"], ["ok"]]

    asyncio.run(scenario())


def test_start_managed_workgroup_ignores_request_output_location(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
) -> None:
    _create_managed_workgroup(workgroups)

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "WorkGroup": "managed",
                "ResultConfiguration": {
                    "OutputLocation": "s3://bucket/request.csv"
                },
            },
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        # A request-carried ResultConfiguration never overrides Athena-owned
        # storage: the stored configuration stays empty.
        assert record.result_configuration == ResultConfiguration()

    asyncio.run(scenario())


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
