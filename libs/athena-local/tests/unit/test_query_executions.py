"""Handler tests for the seven query-plane operations.

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
from athena_local.common_schemas import (
    ManagedQueryResultsConfiguration,
    ResultConfiguration,
)
from athena_local.data_catalog_state import DataCatalogStore
from athena_local.dispatch import implemented_operations
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
from athena_local.main import reset_query_plane
from athena_local.query_executions import (
    batch_get_query_execution,
    get_query_execution,
    get_query_results,
    get_query_runtime_statistics,
    list_query_executions,
    register_query_execution_handlers,
    start_query_execution,
    stop_query_execution,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore
from athena_local.trino_client import TrinoColumn, TrinoPage
from athena_local.workgroup_schemas import WorkGroupConfiguration

QUERY_OPERATIONS = {
    "StartQueryExecution",
    "StopQueryExecution",
    "GetQueryExecution",
    "BatchGetQueryExecution",
    "GetQueryResults",
    "GetQueryRuntimeStatistics",
    "ListQueryExecutions",
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


@pytest.fixture()
def prepared_statements() -> PreparedStatementStore:
    return PreparedStatementStore()


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
        assert _page_value_names(result_set) == [["col"], ["ok"]]

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
    catalogs.create("lambda_cat", "LAMBDA", None, {})

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
    catalogs.create("extra_glue", "GLUE", None, {})

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
    record = _succeeded_result(store, [["1"]])

    output = asyncio.run(
        stop_query_execution(
            executor, {"QueryExecutionId": record.query_execution_id}
        )
    )

    # The model marks the op idempotent: a terminal execution answers 200
    # unchanged — the fake client's AssertionError proves no Trino DELETE ran.
    assert output == {}
    assert record.state == SUCCEEDED


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
    record = _succeeded_result(
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
    record = _succeeded_result(
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


def _page_value_names(result_set: object) -> list[list[str]]:
    """Reduce a wire ResultSet to its cells' VarCharValue strings."""
    rows = result_set["Rows"]  # type: ignore[index]
    assert isinstance(rows, list)
    names: list[list[str]] = []
    for row in rows:
        data = row["Data"]  # type: ignore[index,literal-required]
        assert isinstance(data, list)
        names.append(
            [
                cell["VarCharValue"]  # type: ignore[index,literal-required]
                for cell in data
                if isinstance(cell, dict) and "VarCharValue" in cell
            ]
        )
    return names


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
