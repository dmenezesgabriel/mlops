"""StartQueryExecution handler tests: execution context,
catalog validation and ExecutionParameters.

``QueryExecutionContext.Catalog`` must name a registered GLUE catalog (the
seeded AwsDataCatalog admits empty stores); ExecutionParameters members must
be a list of strings and reach the record verbatim.
"""

from __future__ import annotations

import asyncio

import pytest
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    SUCCEEDED,
    ExecutionStore,
)
from athena_local.executor import QueryExecutor
from athena_local.query_executions import (
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


@pytest.fixture()
def catalogs() -> DataCatalogStore:
    return DataCatalogStore()


def test_start_rejects_unregistered_catalog(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
) -> None:
    # AWS rejects a submission naming a catalog no CreateDataCatalog
    # registered; the emulator validates the same at submit.
    with pytest.raises(InvalidRequestException, match="does not exist"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "QueryExecutionContext": {"Catalog": "ghost"},
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
                data_catalog_store=catalogs,
            )
        )
    assert store.by_id == {}  # rejected before any execution was queued


def test_start_rejects_non_glue_registered_catalog(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
) -> None:
    # A registered catalog of any other DataCatalogType names a data source
    # the emulator cannot run (federated/lambda/external Hive); accepting it
    # would silently execute on the Glue-backed catalog instead.
    catalogs.create("lambda_cat", "LAMBDA", None, {}, [])

    with pytest.raises(InvalidRequestException, match="GLUE"):
        asyncio.run(
            start_query_execution(
                executor,
                workgroups,
                {
                    "QueryString": "SELECT 1",
                    "QueryExecutionContext": {"Catalog": "lambda_cat"},
                    "ResultConfiguration": {
                        "OutputLocation": "s3://bucket/q.csv"
                    },
                },
                data_catalog_store=catalogs,
            )
        )
    assert store.by_id == {}  # rejected before any execution was queued


def test_start_accepts_seeded_aws_data_catalog(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "QueryExecutionContext": {"Catalog": "AwsDataCatalog"},
                "ResultConfiguration": {"OutputLocation": "s3://b/"},
            },
            data_catalog_store=catalogs,
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.state == SUCCEEDED
        assert record.catalog == "AwsDataCatalog"

    asyncio.run(scenario())


def test_start_accepts_registered_glue_catalog(
    store: ExecutionStore,
    executor: QueryExecutor,
    workgroups: WorkGroupStore,
    catalogs: DataCatalogStore,
) -> None:
    catalogs.create("extra_glue", "GLUE", None, {}, [])

    async def scenario() -> None:
        output = await start_query_execution(
            executor,
            workgroups,
            {
                "QueryString": "SELECT 1",
                "QueryExecutionContext": {"Catalog": "extra_glue"},
                "ResultConfiguration": {"OutputLocation": "s3://b/"},
            },
            data_catalog_store=catalogs,
        )

        record = store.get(output["QueryExecutionId"])
        await executor._tasks[record.query_execution_id]
        assert record.state == SUCCEEDED
        assert record.catalog == "extra_glue"

    asyncio.run(scenario())


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
