"""Shared named fakes for query-plane handler tests.

``TerminalStatementClient`` serves a single FINISHED page so started
executions complete immediately; ``RecordingResultWriter`` records every
persisted execution (F.I.R.S.T., no docker).
"""

from __future__ import annotations

from athena_local.executions import (
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.trino_client import TrinoColumn, TrinoPage


def terminal_page() -> TrinoPage:
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
        self,
        query: str,
        catalog: str,
        schema: str,
        user: str,
        session_properties: dict[str, str] | None = None,
    ) -> TrinoPage:
        return terminal_page()

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


def succeeded_result(
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


def page_values(row: dict[str, object]) -> list[str]:
    """Strip a wire Row down to its VarCharValue cell strings."""
    data = row["Data"]
    assert isinstance(data, list)
    return [
        cell["VarCharValue"]
        for cell in data
        if isinstance(cell, dict) and "VarCharValue" in cell
    ]


def page_value_names(result_set: object) -> list[list[str]]:
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
