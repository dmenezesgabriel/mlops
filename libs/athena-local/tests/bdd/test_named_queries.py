"""Step definitions for the named query BDD feature (MD-2).

Steps exercise the handler layer directly against a fresh in-memory registry
per scenario — the same boundary pytest-bdd asserts for the canonical model —
so the feature runs without HTTP or docker while pinning the JSON-1.1 wire
behavior consumers depend on. Parametrized steps use ``parsers.parse`` so the
quoted values in the feature file are captured (pytest-bdd 8 no longer turns
plain step strings into capture patterns).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from athena_local.errors import AthenaError, InvalidRequestException
from athena_local.named_queries import (
    batch_get_named_query,
    create_named_query,
    delete_named_query,
    get_named_query,
    list_named_queries,
)
from athena_local.state import NamedQueryStore
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("named_queries.feature")


@dataclass
class NamedQueryOutcome:
    """State shared between the when and then steps of a scenario."""

    error: AthenaError | None = None
    last_success: dict[str, object] | None = None
    created_ids: list[str] = None
    next_token: str | None = None


@pytest.fixture
def named_query_store() -> NamedQueryStore:
    return NamedQueryStore()


@pytest.fixture
def outcome() -> NamedQueryOutcome:
    return NamedQueryOutcome(created_ids=[])


@given("a fresh named query registry")
def _fresh_registry(
    named_query_store: NamedQueryStore, outcome: NamedQueryOutcome
) -> None:
    assert named_query_store.list("primary")[0] == []
    outcome.created_ids = []
    outcome.next_token = None


@when(parsers.parse('a named query named "{name}" is created'))
def _create_named_query(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    name: str,
) -> None:
    output = create_named_query(
        named_query_store,
        {
            "Name": name,
            "Database": "sampledb",
            "QueryString": "SELECT * FROM flights",
        },
    )
    outcome.created_ids.append(output["NamedQueryId"])


@when(
    parsers.parse(
        'a named query named "{name}" is created in the "{workgroup}" workgroup'
    )
)
def _create_named_query_in_workgroup(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    name: str,
    workgroup: str,
) -> None:
    output = create_named_query(
        named_query_store,
        {
            "Name": name,
            "Database": "sampledb",
            "QueryString": "SELECT * FROM flights",
            "WorkGroup": workgroup,
        },
    )
    outcome.created_ids.append(output["NamedQueryId"])


@when(parsers.parse("GetNamedQuery targets a non-existent query ID"))
def _get_missing_query(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    try:
        get_named_query(named_query_store, {"NamedQueryId": "missing-id"})
    except AthenaError as error:
        outcome.error = error


@when(
    parsers.parse(
        '{num:d} named queries are created in the "{workgroup}" workgroup'
    )
)
def _create_multiple_queries(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    num: int,
    workgroup: str,
) -> None:
    for i in range(num):
        output = create_named_query(
            named_query_store,
            {
                "Name": f"query{i}",
                "Database": "sampledb",
                "QueryString": f"SELECT {i}",
                "WorkGroup": workgroup,
            },
        )
        outcome.created_ids.append(output["NamedQueryId"])


@when(parsers.parse("ListNamedQueries requests MaxResults {num:d}"))
def _list_with_max_results(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    num: int,
) -> None:
    outcome.last_success = list_named_queries(
        named_query_store, {"WorkGroup": "analytics", "MaxResults": num}
    )


@when(
    parsers.parse(
        "ListNamedQueries requests MaxResults {num:d} with the NextToken"
    )
)
def _list_with_next_token(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    num: int,
) -> None:
    outcome.last_success = list_named_queries(
        named_query_store,
        {
            "WorkGroup": "analytics",
            "MaxResults": num,
            "NextToken": outcome.next_token,
        },
    )


@when(parsers.parse("DeleteNamedQuery targets the created query ID"))
def _delete_created_query(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    delete_named_query(
        named_query_store, {"NamedQueryId": outcome.created_ids[0]}
    )


@given(parsers.parse("{num:d} named queries are created"))
@when(parsers.parse("{num:d} named queries are created"))
def _create_queries_without_workgroup(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    num: int,
) -> None:
    for i in range(num):
        output = create_named_query(
            named_query_store,
            {
                "Name": f"query{i}",
                "Database": "sampledb",
                "QueryString": f"SELECT {i}",
            },
        )
        outcome.created_ids.append(output["NamedQueryId"])


@when(parsers.parse("{num:d} named query is created"))
def _create_query_singular(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    num: int,
) -> None:
    _create_queries_without_workgroup(outcome, named_query_store, num)


@when(parsers.parse("BatchGetNamedQuery requests both query IDs"))
def _batch_get_both(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    outcome.last_success = batch_get_named_query(
        named_query_store, {"NamedQueryIds": outcome.created_ids}
    )


@when(
    parsers.parse(
        "BatchGetNamedQuery requests the created ID and {num:d} missing IDs"
    )
)
def _batch_get_with_missing(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
    num: int,
) -> None:
    missing_ids = [f"missing-{i}" for i in range(num)]
    outcome.last_success = batch_get_named_query(
        named_query_store,
        {"NamedQueryIds": [outcome.created_ids[0]] + missing_ids},
    )


@then("GetNamedQuery returns the query details")
def _get_returns_details(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    query = get_named_query(
        named_query_store, {"NamedQueryId": outcome.created_ids[0]}
    )["NamedQuery"]
    assert query["Name"] == "flights_query"
    assert query["Database"] == "sampledb"
    assert query["QueryString"] == "SELECT * FROM flights"


@then('the query is scoped to the "primary" workgroup')
def _scoped_to_primary(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    query = get_named_query(
        named_query_store, {"NamedQueryId": outcome.created_ids[0]}
    )["NamedQuery"]
    assert query["WorkGroup"] == "primary"


@then('GetNamedQuery returns the query with workgroup "analytics"')
def _returns_analytics_workgroup(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    query = get_named_query(
        named_query_store, {"NamedQueryId": outcome.created_ids[0]}
    )["NamedQuery"]
    assert query["WorkGroup"] == "analytics"


@then('ListNamedQueries for "analytics" includes the query ID')
def _list_includes_id(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    ids = list_named_queries(named_query_store, {"WorkGroup": "analytics"})[
        "NamedQueryIds"
    ]
    assert outcome.created_ids[0] in ids


@then("GetNamedQuery answers InvalidRequestException")
def _get_error_shape(outcome: NamedQueryOutcome) -> None:
    assert isinstance(outcome.error, InvalidRequestException)


@then("the response contains 2 query IDs")
def _response_has_2_ids(outcome: NamedQueryOutcome) -> None:
    assert len(outcome.last_success["NamedQueryIds"]) == 2


@then("a NextToken is returned")
def _next_token_returned(outcome: NamedQueryOutcome) -> None:
    assert "NextToken" in outcome.last_success
    outcome.next_token = outcome.last_success["NextToken"]


@then("the response contains 2 more query IDs")
def _response_has_2_more_ids(outcome: NamedQueryOutcome) -> None:
    assert len(outcome.last_success["NamedQueryIds"]) == 2


@then("the response contains 1 query ID")
def _response_has_1_id(outcome: NamedQueryOutcome) -> None:
    assert len(outcome.last_success["NamedQueryIds"]) == 1


@then("no NextToken is returned")
def _no_next_token(outcome: NamedQueryOutcome) -> None:
    assert "NextToken" not in outcome.last_success


@then("GetNamedQuery for the deleted ID answers InvalidRequestException")
def _get_deleted_error(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    try:
        get_named_query(
            named_query_store, {"NamedQueryId": outcome.created_ids[0]}
        )
    except InvalidRequestException:
        pass
    else:
        raise AssertionError("Expected InvalidRequestException")


@then("ListNamedQueries no longer includes the query ID")
def _list_excludes_id(
    outcome: NamedQueryOutcome,
    named_query_store: NamedQueryStore,
) -> None:
    ids = list_named_queries(named_query_store, None)["NamedQueryIds"]
    assert outcome.created_ids[0] not in ids


@then("the response contains both NamedQuery objects")
def _response_has_2_queries(outcome: NamedQueryOutcome) -> None:
    assert len(outcome.last_success["NamedQueries"]) == 2


@then("no UnprocessedNamedQueryIds are returned")
def _no_unprocessed(outcome: NamedQueryOutcome) -> None:
    assert "UnprocessedNamedQueryIds" not in outcome.last_success


@then("the response contains 1 NamedQuery object")
def _response_has_1_query(outcome: NamedQueryOutcome) -> None:
    assert len(outcome.last_success["NamedQueries"]) == 1


@then("2 UnprocessedNamedQueryIds are returned")
def _has_2_unprocessed(outcome: NamedQueryOutcome) -> None:
    assert len(outcome.last_success["UnprocessedNamedQueryIds"]) == 2
