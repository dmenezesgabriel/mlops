"""Step definitions for the inline-results BDD feature (AR-3).

Steps drive the shipped handler — ``get_query_results`` over a real
``QueryExecutor`` — against a fresh in-memory store per scenario, so the
feature pins the MaxResults / NextToken wire handshake consumers rely on
without HTTP, moto, or docker (F.I.R.S.T., mirroring the workgroup BDD
harness).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.executions import (
    RUNNING,
    SUCCEEDED,
    ExecutionStore,
    QueryExecutionRecord,
)
from athena_local.executor import QueryExecutor
from athena_local.query_executions import get_query_results
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("query_executions.feature")


class _UnusedStatementClient:
    """The inline-read harness only exercises ``ensure_query_finished``."""


class _UnusedArtifactWriter:
    """The inline-read harness only exercises ``ensure_query_finished``."""


@dataclass
class QueryResultsOutcome:
    """State shared between the when and then steps of a scenario."""

    store: ExecutionStore = field(default_factory=ExecutionStore)
    record: QueryExecutionRecord | None = None
    executor: QueryExecutor = field(init=False)
    response: dict[str, object] | None = None
    error: InvalidRequestException | None = None

    def __post_init__(self) -> None:
        self.executor = QueryExecutor(
            store=self.store,
            client=_UnusedStatementClient(),
            writer=_UnusedArtifactWriter(),
        )


@pytest.fixture
def outcome() -> QueryResultsOutcome:
    return QueryResultsOutcome()


@given(parsers.re(r"a SUCCEEDED query result with (?P<count>\d+) row(?:s)?"))
def _succeeded_result(outcome: QueryResultsOutcome, count: str) -> None:
    row_count = int(count)
    record = outcome.store.create(query="SELECT 1", workgroup="primary")
    record.transition_to(RUNNING)
    record.cache_result_page(
        [("id", "integer")],
        [[str(number)] for number in range(1, row_count + 1)],
    )
    record.transition_to(SUCCEEDED)
    outcome.record = record


@when(parsers.parse("GetQueryResults requests MaxResults {count:d}"))
def _request_max_results(outcome: QueryResultsOutcome, count: int) -> None:
    _call(outcome, {"MaxResults": count})


@when(
    parsers.parse(
        "GetQueryResults continues with the NextToken and MaxResults {count:d}"
    )
)
def _continue_with_token(outcome: QueryResultsOutcome, count: int) -> None:
    assert outcome.response is not None
    next_token = outcome.response.get("NextToken")
    assert isinstance(next_token, str), "previous page carried no NextToken"
    _call(outcome, {"NextToken": next_token, "MaxResults": count})


@when(parsers.parse('GetQueryResults requests NextToken "{token}"'))
def _request_with_token(outcome: QueryResultsOutcome, token: str) -> None:
    _call(outcome, {"NextToken": token})


@then(
    parsers.parse(
        "the page has the header and {count:d} data rows and a NextToken"
    )
)
def _header_page(outcome: QueryResultsOutcome, count: int) -> None:
    assert outcome.response is not None
    rows = outcome.response["ResultSet"]["Rows"]
    assert isinstance(rows, list)
    assert _page_values(rows[0]) == ["id"]
    assert len(rows) == count + 1
    assert "NextToken" in outcome.response


@then(parsers.parse("the page has {count:d} data rows and a NextToken"))
def _data_page_with_token(outcome: QueryResultsOutcome, count: int) -> None:
    assert outcome.response is not None
    rows = outcome.response["ResultSet"]["Rows"]
    assert isinstance(rows, list)
    assert len(rows) == count
    assert "NextToken" in outcome.response


@then(parsers.parse("the page has {count:d} data row and no NextToken"))
def _last_page(outcome: QueryResultsOutcome, count: int) -> None:
    assert outcome.response is not None
    rows = outcome.response["ResultSet"]["Rows"]
    assert isinstance(rows, list)
    assert len(rows) == count
    assert "NextToken" not in outcome.response


@then(
    parsers.parse(
        'the request fails with InvalidRequestException naming "{value}"'
    )
)
def _failed_naming_value(outcome: QueryResultsOutcome, value: str) -> None:
    assert outcome.error is not None
    assert value in str(outcome.error)


@then('the request fails with InvalidRequestException "Invalid NextToken"')
def _failed_invalid_token(outcome: QueryResultsOutcome) -> None:
    assert outcome.error is not None
    assert "Invalid NextToken" in str(outcome.error)


def _call(outcome: QueryResultsOutcome, members: dict[str, object]) -> None:
    """Run the handler, capturing either the response or the shaped error."""
    assert outcome.record is not None
    outcome.error = None
    outcome.response = None
    payload: dict[str, object] = {
        "QueryExecutionId": outcome.record.query_execution_id
    }
    payload.update(members)
    try:
        outcome.response = get_query_results(
            outcome.store, outcome.executor, payload
        )
    except InvalidRequestException as error:
        outcome.error = error


def _page_values(row: object) -> list[str]:
    """Strip a wire Row down to its VarCharValue cell strings."""
    data = row["Data"]  # type: ignore[index,literal-required]
    assert isinstance(data, list)
    return [
        cell["VarCharValue"]
        for cell in data
        if isinstance(cell, dict) and "VarCharValue" in cell
    ]
