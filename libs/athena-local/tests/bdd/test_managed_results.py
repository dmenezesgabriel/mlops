"""Step definitions for the managed-results BDD feature.

Steps drive the shipped handlers — ``start_query_execution`` / ``get_query_
execution`` / ``get_query_results`` over a real ``QueryExecutor`` with a
terminal statement client — against a fresh in-memory workgroup and execution
store per scenario. The recording writer proves a managed execution reaches
SUCCEEDED without any artifact write (ADR-0011), pinning the wire shape
wrangler's managed path reads (awswrangler/athena/_read.py:450).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest
from athena_local.common_schemas import (
    ManagedQueryResultsConfiguration,
    ResultConfiguration,
)
from athena_local.executions import (
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.executor import QueryExecutor
from athena_local.query_executions import (
    get_query_execution,
    get_query_results,
    start_query_execution,
)
from athena_local.state import WorkGroupStore
from athena_local.trino_client import TrinoColumn, TrinoPage
from athena_local.workgroup_schemas import WorkGroupConfiguration
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("managed_results.feature")


class _TerminalStatementClient:
    """StatementClient fake serving one finished page."""

    async def submit_statement(
        self,
        query: str,
        catalog: str,
        schema: str,
        user: str,
        session_properties: dict[str, str] | None = None,
    ) -> TrinoPage:
        return TrinoPage(
            query_id="q",
            next_uri=None,
            update_type=None,
            columns=[TrinoColumn(name="col", column_type="varchar")],
            data=[["ok"]],
            stats={
                "state": "FINISHED",
                "processedBytes": 64,
                "wallTimeMillis": 5,
            },
            error=None,
        )

    async def fetch_next(self, next_uri: str) -> None:
        raise AssertionError("single-page submissions never poll Trino")

    async def cancel(self, next_uri: str) -> None:
        raise AssertionError("managed-results BDD never cancels Trino")


class _RecordingWriter:
    """ResultArtifactWriter fake; managed runs must never call it (ADR-0011)."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def write(
        self, execution: QueryExecutionRecord, final_page: TrinoPage
    ) -> None:
        self.calls += 1


@dataclass
class ManagedResultsOutcome:
    """State shared between the when and then steps of a scenario."""

    workgroups: WorkGroupStore = field(default_factory=WorkGroupStore)
    store: ExecutionStore = field(default_factory=ExecutionStore)
    writer: _RecordingWriter = field(default_factory=_RecordingWriter)
    executor: QueryExecutor = field(init=False)
    query_execution_id: str | None = None

    def __post_init__(self) -> None:
        self.executor = QueryExecutor(
            store=self.store,
            client=_TerminalStatementClient(),
            writer=self.writer,
        )


@pytest.fixture
def outcome() -> ManagedResultsOutcome:
    return ManagedResultsOutcome()


@given("a managed-results query harness")
def _fresh_harness(outcome: ManagedResultsOutcome) -> None:
    assert outcome.workgroups.get("primary").name == "primary"


@given(
    parsers.parse(
        'a workgroup named "{name}" with managed query results enabled'
    )
)
def _managed_workgroup(outcome: ManagedResultsOutcome, name: str) -> None:
    outcome.workgroups.create(
        name,
        WorkGroupConfiguration(
            managed_query_results_configuration=(
                ManagedQueryResultsConfiguration(enabled=True)
            )
        ),
        None,
        [],
    )


@when(
    parsers.parse(
        "StartQueryExecution runs SELECT 1 on it without an output location"
    )
)
def _start_without_location(outcome: ManagedResultsOutcome) -> None:
    async def scenario() -> None:
        output = await start_query_execution(
            outcome.executor,
            outcome.workgroups,
            {"QueryString": "SELECT 1", "WorkGroup": "managed"},
        )
        record = outcome.store.get(output["QueryExecutionId"])
        await outcome.executor._tasks[record.query_execution_id]
        outcome.query_execution_id = output["QueryExecutionId"]

    asyncio.run(scenario())


@then("the execution succeeds and the writer was not called")
def _succeeded_without_write(outcome: ManagedResultsOutcome) -> None:
    record = _record(outcome)
    assert record.state == "SUCCEEDED"
    assert outcome.writer.calls == 0
    assert record.result_configuration == ResultConfiguration()


@then("GetQueryExecution reports ResultConfiguration without OutputLocation")
def _no_output_location(outcome: ManagedResultsOutcome) -> None:
    payload = get_query_execution(
        outcome.store, {"QueryExecutionId": _execution_id(outcome)}
    )["QueryExecution"]
    result_configuration = payload["ResultConfiguration"]
    assert "OutputLocation" not in result_configuration


@then("GetQueryResults serves the inline rows")
def _inline_rows(outcome: ManagedResultsOutcome) -> None:
    result_set = get_query_results(
        outcome.store,
        outcome.executor,
        {"QueryExecutionId": _execution_id(outcome)},
    )["ResultSet"]
    rows = result_set["Rows"]
    assert isinstance(rows, list)
    assert _cell_values(rows[0]) == ["col"]
    assert _cell_values(rows[1]) == ["ok"]


def _record(outcome: ManagedResultsOutcome) -> QueryExecutionRecord:
    return outcome.store.get(_execution_id(outcome))


def _execution_id(outcome: ManagedResultsOutcome) -> str:
    assert outcome.query_execution_id is not None
    return outcome.query_execution_id


def _cell_values(row: object) -> list[str]:
    data = row["Data"]  # type: ignore[index,literal-required]
    assert isinstance(data, list)
    return [
        cell["VarCharValue"]  # type: ignore[index,literal-required]
        for cell in data
        if isinstance(cell, dict) and "VarCharValue" in cell
    ]
