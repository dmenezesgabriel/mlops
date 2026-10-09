"""Handler tests for the five named query operations.

Handlers translate a parsed JSON payload into the operation's output shape,
delegating registry semantics to ``NamedQueryStore``. The payload-shape
contract lives in the service model; these tests fix the wire-facing behavior:
output keys match the canonical service-2.json output members.
"""

from __future__ import annotations

from collections.abc import Callable

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
from athena_local.state import NamedQueryStore, WorkGroupStore
from athena_local.workgroup_schemas import WorkGroupConfiguration

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


@pytest.fixture()
def workgroups() -> WorkGroupStore:
    return WorkGroupStore()


def test_named_query_operations_are_registered() -> None:
    # main.py is the composition root (ADR-0003); importing it registers the
    # five named query operations against the app's store exactly once.
    import athena_local.main  # noqa: F401

    assert NAMED_QUERY_OPERATIONS <= implemented_operations()


def test_create_named_query_returns_id(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    output = create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    output = create_named_query(
        store,
        workgroups,
        {
            "Name": "test_query",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )

    record = store.get(output["NamedQueryId"])
    assert record.workgroup == "primary"


def test_create_named_query_disabled_workgroup_is_shaped_error(
    store: NamedQueryStore,
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
        create_named_query(
            store,
            workgroups,
            {
                "Name": "test_query",
                "Database": "db",
                "QueryString": "SELECT 1",
                "WorkGroup": "blocked",
            },
        )


def test_create_named_query_requires_name(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    with pytest.raises(InvalidRequestException, match="Name"):
        create_named_query(
            store,
            workgroups,
            {
                "Database": "db",
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_requires_database(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Database"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "test",
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_requires_query_string(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryString"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "test",
                "Database": "db",
            },
        )


def test_get_named_query_returns_full_record(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    create_output = create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        get_named_query(store, {"NamedQueryId": "missing-id"})


def test_list_named_queries_returns_ids_by_workgroup(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    create_named_query(
        store,
        workgroups,
        {
            "Name": "query1",
            "Database": "db",
            "QueryString": "SELECT 1",
            "WorkGroup": "analytics",
        },
    )
    create_named_query(
        store,
        workgroups,
        {
            "Name": "query2",
            "Database": "db",
            "QueryString": "SELECT 2",
            "WorkGroup": "analytics",
        },
    )
    create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    output = list_named_queries(store, {"WorkGroup": "nonexistent"})

    assert output["NamedQueryIds"] == []
    assert "NextToken" not in output


def test_list_named_queries_with_max_results(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    for i in range(5):
        create_named_query(
            store,
            workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    for i in range(5):
        create_named_query(
            store,
            workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Invalid NextToken"):
        list_named_queries(
            store, {"WorkGroup": "primary", "NextToken": "invalid"}
        )


@pytest.mark.parametrize("max_results", [-1, 51])
def test_list_named_queries_rejects_out_of_bounds_max_results(
    store: NamedQueryStore, max_results: int
) -> None:
    # Model MaxNamedQueriesCount: 0..50 (service-2.json).
    with pytest.raises(InvalidRequestException, match="MaxResults"):
        list_named_queries(store, {"MaxResults": max_results})


def test_list_named_queries_accepts_zero_max_results(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    # 0 is legal (model min 0): offset_page's <=0 no-limit branch answers the
    # full page with no NextToken — a 0-item page plus token would loop a
    # paginator forever.
    create_named_query(
        store,
        workgroups,
        {
            "Name": "query1",
            "Database": "db",
            "QueryString": "SELECT 1",
            "WorkGroup": "analytics",
        },
    )

    output = list_named_queries(
        store, {"WorkGroup": "analytics", "MaxResults": 0}
    )

    assert len(output["NamedQueryIds"]) == 1
    assert "NextToken" not in output


def test_delete_named_query_removes_from_store(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    create_output = create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="does not exist"):
        delete_named_query(store, {"NamedQueryId": "missing-id"})


def test_batch_get_named_query_returns_found_records(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    id1 = create_named_query(
        store,
        workgroups,
        {
            "Name": "query1",
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )["NamedQueryId"]
    id2 = create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    id1 = create_named_query(
        store,
        workgroups,
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
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="must not be empty"):
        batch_get_named_query(store, {"NamedQueryIds": []})


def test_batch_get_named_query_requires_list_of_strings(
    store: NamedQueryStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(
        InvalidRequestException, match="must contain only strings"
    ):
        batch_get_named_query(store, {"NamedQueryIds": [123]})


def test_batch_get_named_query_rejects_over_fifty_ids(
    store: NamedQueryStore,
) -> None:
    # Model NamedQueryIdList caps at 50 members (service-2.json).
    with pytest.raises(InvalidRequestException, match="NamedQueryIds"):
        batch_get_named_query(
            store, {"NamedQueryIds": [f"id-{i}" for i in range(51)]}
        )

    output = batch_get_named_query(
        store, {"NamedQueryIds": [f"id-{i}" for i in range(50)]}
    )
    assert len(output["UnprocessedNamedQueryIds"]) == 50


def test_create_named_query_rejects_oversized_name(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    # Model NameString: 1..128 (service-2.json).
    with pytest.raises(InvalidRequestException, match="at most 128"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "n" * 129,
                "Database": "db",
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_accepts_boundary_name(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    output = create_named_query(
        store,
        workgroups,
        {
            "Name": "n" * 128,
            "Database": "db",
            "QueryString": "SELECT 1",
        },
    )
    assert store.get(output["NamedQueryId"]).name == "n" * 128


def test_create_named_query_rejects_empty_description(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    # Model DescriptionString min 1: an explicit "" 400s while an absent
    # Description keeps the "" store default.
    with pytest.raises(InvalidRequestException, match="at least 1"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "q",
                "Description": "",
                "Database": "db",
                "QueryString": "SELECT 1",
            },
        )

    output = create_named_query(
        store,
        workgroups,
        {"Name": "q2", "Database": "db", "QueryString": "SELECT 1"},
    )
    assert store.get(output["NamedQueryId"]).description == ""


def test_create_named_query_rejects_oversized_description(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    # Model DescriptionString max 1024.
    with pytest.raises(InvalidRequestException, match="at most 1024"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "q",
                "Description": "d" * 1025,
                "Database": "db",
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_rejects_oversized_database(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    # Model DatabaseString: 1..255.
    with pytest.raises(InvalidRequestException, match="at most 255"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "q",
                "Database": "d" * 256,
                "QueryString": "SELECT 1",
            },
        )


def test_create_named_query_rejects_oversized_query_string(
    store: NamedQueryStore, workgroups: WorkGroupStore
) -> None:
    # Model QueryString max 262144 — the same bound StartQueryExecution
    # enforces on the submit path.
    with pytest.raises(InvalidRequestException, match="at most 262144"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "q",
                "Database": "db",
                "QueryString": "x" * 262145,
            },
        )


@pytest.mark.parametrize(
    "workgroup", ["bad name!", "../escape", "with/slash", "a" * 129]
)
def test_create_named_query_rejects_non_canonical_workgroup(
    store: NamedQueryStore, workgroups: WorkGroupStore, workgroup: str
) -> None:
    # WorkGroupName pattern [a-zA-Z0-9._-]{1,128} (service-2.json). Match the
    # constraint message: the unknown-workgroup pass-through would otherwise
    # CREATE the record, so a bare "WorkGroup" match can false-green.
    with pytest.raises(InvalidRequestException, match="must match pattern"):
        create_named_query(
            store,
            workgroups,
            {
                "Name": "q",
                "Database": "db",
                "QueryString": "SELECT 1",
                "WorkGroup": workgroup,
            },
        )


@pytest.mark.parametrize("workgroup", ["bad name!", "with/slash"])
def test_list_named_queries_rejects_non_canonical_workgroup(
    store: NamedQueryStore, workgroup: str
) -> None:
    with pytest.raises(InvalidRequestException, match="must match pattern"):
        list_named_queries(store, {"WorkGroup": workgroup})


@pytest.mark.parametrize("operation", [get_named_query, delete_named_query])
@pytest.mark.parametrize("query_id", ["has space", "x" * 129])
def test_named_query_id_member_rejects_non_canonical_ids(
    store: NamedQueryStore,
    operation: Callable[
        [NamedQueryStore, dict[str, object]], dict[str, object]
    ],
    query_id: str,
) -> None:
    # Model NamedQueryId: \S+ 1..128. Match the constraint message — the
    # store's "does not exist" would satisfy a bare "NamedQueryId" match
    # without any parse-layer check.
    with pytest.raises(
        InvalidRequestException, match="must match pattern|at most 128"
    ):
        operation(store, {"NamedQueryId": query_id})


@pytest.mark.parametrize("member_id", ["has space", "", "x" * 129])
def test_batch_get_named_query_rejects_non_canonical_member_ids(
    store: NamedQueryStore, member_id: str
) -> None:
    # NamedQueryIdList members are NamedQueryId-shaped (\S+ 1..128).
    with pytest.raises(InvalidRequestException, match=r"NamedQueryIds\[0\]"):
        batch_get_named_query(store, {"NamedQueryIds": [member_id]})
