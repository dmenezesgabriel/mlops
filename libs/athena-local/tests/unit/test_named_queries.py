"""Handler tests for the five named query operations (MD-2).

Handlers translate a parsed JSON payload into the operation's output shape,
delegating registry semantics to ``NamedQueryStore``. The payload-shape
contract lives in the service model; these tests fix the wire-facing behavior:
output keys match the canonical service-2.json output members.
"""

from __future__ import annotations

import pytest
from athena_local.dispatch import implemented_operations
from athena_local.errors import InvalidRequestException
from athena_local.named_queries import (
    batch_get_named_query,
    create_named_query,
    delete_named_query,
    get_named_query,
    list_named_queries,
)
from athena_local.state import NamedQueryStore

NAMED_QUERY_OPERATIONS = {
    "CreateNamedQuery",
    "GetNamedQuery",
    "ListNamedQueries",
    "DeleteNamedQuery",
    "BatchGetNamedQuery",
}


@pytest.fixture()
def store() -> NamedQueryStore:
    return NamedQueryStore()


def test_named_query_operations_are_registered() -> None:
    # main.py is the composition root (ADR-0003); importing it registers the
    # five named query operations against the app's store exactly once.
    import athena_local.main  # noqa: F401

    assert NAMED_QUERY_OPERATIONS <= implemented_operations()


def test_create_named_query_returns_id(store: NamedQueryStore) -> None:
    output = create_named_query(
        store,
        {
            "Name": "flights_query",
            "Description": "Flights from Seattle",
            "Database": "sampledb",
            "QueryString": "SELECT * FROM flights",
            "WorkGroup": "analytics",
        },
    )

    assert "NamedQueryId" in output
    assert isinstance(output["NamedQueryId"], str)
    record = store.get(output["NamedQueryId"])
    assert record.name == "flights_query"
    assert record.description == "Flights from Seattle"
    assert record.database == "sampledb"
    assert record.query_string == "SELECT * FROM flights"
    assert record.workgroup == "analytics"


def test_create_named_query_defaults_to_primary_workgroup(
    store: NamedQueryStore,
) -> None:
    output = create_named_query(
        store,
        {
            "Name": "test_query",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )

    record = store.get(output["NamedQueryId"])
    assert record.workgroup == "primary"


def test_create_named_query_requires_name(store: NamedQueryStore) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        create_named_query(
            store,
            {
                "Database": "db",
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_requires_database(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Database"):
        create_named_query(
            store,
            {
                "Name": "test",
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_requires_query_string(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryString"):
        create_named_query(
            store,
            {
                "Name": "test",
                "Database": "db",
            },
        )


def test_get_named_query_returns_full_record(
    store: NamedQueryStore,
) -> None:
    create_output = create_named_query(
        store,
        {
            "Name": "complex_query",
            "Description": "Complex join",
            "Database": "analytics",
            "QueryString": "SELECT a.* FROM a JOIN b ON a.id = b.id",
            "WorkGroup": "data_science",
        },
    )

    output = get_named_query(
        store, {"NamedQueryId": create_output["NamedQueryId"]}
    )

    query = output["NamedQuery"]
    assert query["Name"] == "complex_query"
    assert query["Description"] == "Complex join"
    assert query["Database"] == "analytics"
    assert query["QueryString"] == "SELECT a.* FROM a JOIN b ON a.id = b.id"
    assert query["WorkGroup"] == "data_science"
    assert "NamedQueryId" in query


def test_get_named_query_missing_raises_invalid_request(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_named_query(store, {"NamedQueryId": "missing-id"})


def test_list_named_queries_returns_ids_by_workgroup(
    store: NamedQueryStore,
) -> None:
    create_named_query(
        store,
        {
            "Name": "query1",
            "Database": "db",
            "QueryString": "SELECT 1",
            "WorkGroup": "analytics",
        },
    )
    create_named_query(
        store,
        {
            "Name": "query2",
            "Database": "db",
            "QueryString": "SELECT 2",
            "WorkGroup": "analytics",
        },
    )
    create_named_query(
        store,
        {
            "Name": "query3",
            "Database": "db",
            "QueryString": "SELECT 3",
            "WorkGroup": "primary",
        },
    )

    output = list_named_queries(store, {"WorkGroup": "analytics"})

    assert len(output["NamedQueryIds"]) == 2
    assert "NextToken" not in output


def test_list_named_queries_defaults_to_primary(
    store: NamedQueryStore,
) -> None:
    create_named_query(
        store,
        {
            "Name": "primary_query",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )

    output = list_named_queries(store, None)

    assert len(output["NamedQueryIds"]) == 1


def test_list_named_queries_empty_workgroup_returns_empty(
    store: NamedQueryStore,
) -> None:
    output = list_named_queries(store, {"WorkGroup": "nonexistent"})

    assert output["NamedQueryIds"] == []
    assert "NextToken" not in output


def test_list_named_queries_with_max_results(
    store: NamedQueryStore,
) -> None:
    for i in range(5):
        create_named_query(
            store,
            {
                "Name": f"query{i}",
                "Database": "db",
                "QueryString": f"SELECT {i}",
                "WorkGroup": "analytics",
            },
        )

    output = list_named_queries(
        store, {"WorkGroup": "analytics", "MaxResults": 2}
    )

    assert len(output["NamedQueryIds"]) == 2
    assert "NextToken" in output


def test_list_named_queries_pagination_round_trip(
    store: NamedQueryStore,
) -> None:
    for i in range(5):
        create_named_query(
            store,
            {
                "Name": f"query{i}",
                "Database": "db",
                "QueryString": f"SELECT {i}",
                "WorkGroup": "analytics",
            },
        )

    page1 = list_named_queries(
        store, {"WorkGroup": "analytics", "MaxResults": 2}
    )
    assert len(page1["NamedQueryIds"]) == 2
    assert "NextToken" in page1

    page2 = list_named_queries(
        store,
        {
            "WorkGroup": "analytics",
            "MaxResults": 2,
            "NextToken": page1["NextToken"],
        },
    )
    assert len(page2["NamedQueryIds"]) == 2
    assert "NextToken" in page2

    page3 = list_named_queries(
        store,
        {
            "WorkGroup": "analytics",
            "MaxResults": 2,
            "NextToken": page2["NextToken"],
        },
    )
    assert len(page3["NamedQueryIds"]) == 1
    assert "NextToken" not in page3


def test_list_named_queries_invalid_next_token_raises(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_named_queries(
            store, {"WorkGroup": "primary", "NextToken": "invalid"}
        )


def test_delete_named_query_removes_from_store(
    store: NamedQueryStore,
) -> None:
    create_output = create_named_query(
        store,
        {
            "Name": "to_delete",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )

    output = delete_named_query(
        store, {"NamedQueryId": create_output["NamedQueryId"]}
    )

    assert output == {}
    with pytest.raises(InvalidRequestException, match="does not exist"):
        store.get(create_output["NamedQueryId"])


def test_delete_named_query_missing_raises_invalid_request(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        delete_named_query(store, {"NamedQueryId": "missing-id"})


def test_batch_get_named_query_returns_found_records(
    store: NamedQueryStore,
) -> None:
    id1 = create_named_query(
        store,
        {
            "Name": "query1",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )["NamedQueryId"]
    id2 = create_named_query(
        store,
        {
            "Name": "query2",
            "Database": "db",
            "QueryString": "SELECT 2",
        },
    )["NamedQueryId"]

    output = batch_get_named_query(store, {"NamedQueryIds": [id1, id2]})

    assert len(output["NamedQueries"]) == 2
    assert "UnprocessedNamedQueryIds" not in output
    names = {q["Name"] for q in output["NamedQueries"]}
    assert names == {"query1", "query2"}


def test_batch_get_named_query_unprocessed_missing_ids(
    store: NamedQueryStore,
) -> None:
    id1 = create_named_query(
        store,
        {
            "Name": "query1",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )["NamedQueryId"]

    output = batch_get_named_query(
        store, {"NamedQueryIds": [id1, "missing-id-1", "missing-id-2"]}
    )

    assert len(output["NamedQueries"]) == 1
    assert output["NamedQueries"][0]["Name"] == "query1"
    assert len(output["UnprocessedNamedQueryIds"]) == 2
    unprocessed_ids = {
        item["NamedQueryId"] for item in output["UnprocessedNamedQueryIds"]
    }
    assert unprocessed_ids == {"missing-id-1", "missing-id-2"}


def test_batch_get_named_query_requires_non_empty_list(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="must not be empty"):
        batch_get_named_query(store, {"NamedQueryIds": []})


def test_batch_get_named_query_requires_list_of_strings(
    store: NamedQueryStore,
) -> None:
    with pytest.raises(
        InvalidRequestException, match="must contain only strings"
    ):
        batch_get_named_query(store, {"NamedQueryIds": [123]})
