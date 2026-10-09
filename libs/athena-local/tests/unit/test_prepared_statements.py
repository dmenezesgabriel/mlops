"""Handler tests for the prepared statement create/read/edit operations.

Handlers translate a parsed JSON payload into the operation's output shape,
delegating registry semantics to ``PreparedStatementStore``. The payload-shape
contract lives in the service model; these tests fix the wire-facing behavior:
output keys match the canonical service-2.json output members.

The key difference from named queries: ``GetPreparedStatement`` raises
``ResourceNotFoundException`` for missing statements per awswrangler expectations
(``research_repos/aws-sdk-pandas/awswrangler/athena/_statements.py:26-29``).
"""

from __future__ import annotations

import pytest
from athena_local.dispatch import implemented_operations
from athena_local.errors import (
    InvalidRequestException,
    ResourceNotFoundException,
)
from athena_local.prepared_statements import (
    batch_get_prepared_statement,
    create_prepared_statement,
    delete_prepared_statement,
    get_prepared_statement,
    update_prepared_statement,
)
from athena_local.request_fields import (
    DESCRIPTION_STRING_MAX_LENGTH,
    QUERY_STRING_MAX_LENGTH,
)
from athena_local.state import PreparedStatementStore, WorkGroupStore
from athena_local.workgroup_schemas import WorkGroupConfiguration

PREPARED_STATEMENT_OPERATIONS = {
    "CreatePreparedStatement",
    "GetPreparedStatement",
    "ListPreparedStatements",
    "UpdatePreparedStatement",
    "DeletePreparedStatement",
    "BatchGetPreparedStatement",
}


@pytest.fixture()
def store() -> PreparedStatementStore:
    return PreparedStatementStore()


@pytest.fixture()
def workgroups() -> WorkGroupStore:
    store = WorkGroupStore()
    # CreatePreparedStatement resolves the workgroup like moto (AF-131), so
    # the non-primary workgroups these tests use must exist up front.
    store.create(
        "analytics", WorkGroupConfiguration(), description=None, tags=[]
    )
    store.create(
        "data_science", WorkGroupConfiguration(), description=None, tags=[]
    )
    return store


def _create_statement(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
    *,
    statement_name: str = "stmt1",
    workgroup: str = "primary",
    query_statement: str = "SELECT 1",
    description: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "StatementName": statement_name,
        "WorkGroup": workgroup,
        "QueryStatement": query_statement,
    }
    if description is not None:
        payload["Description"] = description
    return create_prepared_statement(store, workgroups, payload)


def test_prepared_statement_operations_are_registered() -> None:
    # main.py is the composition root (ADR-0003); importing it registers the
    # six prepared statement operations against the app's store exactly once.
    import athena_local.main  # noqa: F401

    assert PREPARED_STATEMENT_OPERATIONS <= implemented_operations()


def test_create_prepared_statement_returns_empty(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    output = create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "flights_stmt",
            "WorkGroup": "analytics",
            "QueryStatement": "SELECT * FROM flights",
            "Description": "Flights query",
        },
    )

    assert output == {}
    record = store.get("flights_stmt", "analytics")
    assert record.statement_name == "flights_stmt"
    assert record.query_statement == "SELECT * FROM flights"
    assert record.description == "Flights query"
    assert record.workgroup == "analytics"


def test_create_prepared_statement_without_description(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    output = create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    assert output == {}
    record = store.get("test_stmt", "primary")
    assert record.description is None


def test_create_prepared_statement_duplicate_raises_invalid_request(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    with pytest.raises(
        InvalidRequestException, match="already exists in workgroup"
    ):
        create_prepared_statement(
            store,
            workgroups,
            {
                "StatementName": "test_stmt",
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 2",
            },
        )


def test_create_prepared_statement_requires_statement_name(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="StatementName"):
        create_prepared_statement(
            store,
            workgroups,
            {
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 1",
            },
        )


def test_create_prepared_statement_disabled_workgroup_is_shaped_error(
    store: PreparedStatementStore,
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
        create_prepared_statement(
            store,
            workgroups,
            {
                "StatementName": "test_stmt",
                "WorkGroup": "blocked",
                "QueryStatement": "SELECT 1",
            },
        )


def test_create_prepared_statement_requires_workgroup(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        create_prepared_statement(
            store,
            workgroups,
            {
                "StatementName": "test",
                "QueryStatement": "SELECT 1",
            },
        )


def test_create_prepared_statement_requires_query_statement(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryStatement"):
        create_prepared_statement(
            store,
            workgroups,
            {
                "StatementName": "test",
                "WorkGroup": "primary",
            },
        )


def test_get_prepared_statement_returns_full_record(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "complex_stmt",
            "WorkGroup": "data_science",
            "QueryStatement": "SELECT a.* FROM a JOIN b ON a.id = b.id",
            "Description": "Complex join",
        },
    )

    output = get_prepared_statement(
        store, {"StatementName": "complex_stmt", "WorkGroup": "data_science"}
    )

    stmt = output["PreparedStatement"]
    assert stmt["StatementName"] == "complex_stmt"
    assert stmt["QueryStatement"] == "SELECT a.* FROM a JOIN b ON a.id = b.id"
    assert stmt["WorkGroupName"] == "data_science"
    assert stmt["Description"] == "Complex join"
    assert "LastModifiedTime" in stmt


def test_get_prepared_statement_missing_raises_resource_not_found(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        get_prepared_statement(
            store, {"StatementName": "missing_stmt", "WorkGroup": "primary"}
        )


def test_update_prepared_statement_modifies_record(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
            "Description": "Original",
        },
    )

    original_record = store.get("test_stmt", "primary")
    original_time = original_record.last_modified_time

    output = update_prepared_statement(
        store,
        {
            "StatementName": "test_stmt",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 2",
            "Description": "Updated",
        },
    )

    assert output == {}
    updated_record = store.get("test_stmt", "primary")
    assert updated_record.query_statement == "SELECT 2"
    assert updated_record.description == "Updated"
    assert updated_record.last_modified_time > original_time


def test_update_prepared_statement_missing_raises_resource_not_found(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        update_prepared_statement(
            store,
            {
                "StatementName": "missing_stmt",
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 1",
            },
        )


def test_delete_prepared_statement_removes_from_store(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "to_delete",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    output = delete_prepared_statement(
        store, {"StatementName": "to_delete", "WorkGroup": "primary"}
    )

    assert output == {}
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        store.get("to_delete", "primary")


def test_delete_prepared_statement_missing_raises_resource_not_found(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(
        ResourceNotFoundException, match="does not exist in workgroup"
    ):
        delete_prepared_statement(
            store, {"StatementName": "missing_stmt", "WorkGroup": "primary"}
        )


def test_batch_get_prepared_statement_returns_found_records(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "stmt1",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "stmt2",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 2",
        },
    )

    output = batch_get_prepared_statement(
        store,
        {"PreparedStatementNames": ["stmt1", "stmt2"], "WorkGroup": "primary"},
    )

    assert len(output["PreparedStatements"]) == 2
    assert "UnprocessedPreparedStatementNames" not in output
    names = {s["StatementName"] for s in output["PreparedStatements"]}
    assert names == {"stmt1", "stmt2"}


def test_batch_get_prepared_statement_unprocessed_missing_names(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    create_prepared_statement(
        store,
        workgroups,
        {
            "StatementName": "stmt1",
            "WorkGroup": "primary",
            "QueryStatement": "SELECT 1",
        },
    )

    output = batch_get_prepared_statement(
        store,
        {
            "PreparedStatementNames": ["stmt1", "missing-1", "missing-2"],
            "WorkGroup": "primary",
        },
    )

    assert len(output["PreparedStatements"]) == 1
    assert output["PreparedStatements"][0]["StatementName"] == "stmt1"
    assert len(output["UnprocessedPreparedStatementNames"]) == 2
    # Missing names surface as UnprocessedPreparedStatementName structures
    # (StatementName member per service-2.json shape — never bare strings).
    unprocessed_names = {
        item["StatementName"]
        for item in output["UnprocessedPreparedStatementNames"]
    }
    assert unprocessed_names == {"missing-1", "missing-2"}


def test_batch_get_prepared_statement_requires_non_empty_list(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="must not be empty"):
        batch_get_prepared_statement(
            store, {"PreparedStatementNames": [], "WorkGroup": "primary"}
        )


def test_batch_get_prepared_statement_requires_list_of_strings(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(
        InvalidRequestException, match="must contain only strings"
    ):
        batch_get_prepared_statement(
            store, {"PreparedStatementNames": [123], "WorkGroup": "primary"}
        )


@pytest.mark.parametrize(
    "statement_name", ["a", "1stmt", "has-hyphen", "x" * 257]
)
def test_create_prepared_statement_rejects_invalid_statement_name(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
    statement_name: str,
) -> None:
    # Model StatementName: [a-zA-Z_][a-zA-Z0-9_@:]{1,256}, max 256 — so a
    # leading digit, a hyphen, the 1-char tail, and 257 chars are all illegal.
    with pytest.raises(InvalidRequestException, match="StatementName"):
        _create_statement(store, workgroups, statement_name=statement_name)


@pytest.mark.parametrize(
    "statement_name",
    ["a_", "stmt_1", "with@colon:and_under", "x" * 256],
)
def test_create_prepared_statement_accepts_valid_statement_name(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
    statement_name: str,
) -> None:
    _create_statement(store, workgroups, statement_name=statement_name)

    assert (
        store.get(statement_name, "primary").statement_name == statement_name
    )


def test_create_prepared_statement_rejects_too_long_query_statement(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="QueryStatement"):
        _create_statement(
            store,
            workgroups,
            query_statement="x" * (QUERY_STRING_MAX_LENGTH + 1),
        )


def test_create_prepared_statement_accepts_max_query_statement(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    query_statement = "x" * QUERY_STRING_MAX_LENGTH

    _create_statement(store, workgroups, query_statement=query_statement)

    assert store.get("stmt1", "primary").query_statement == query_statement


def test_create_prepared_statement_rejects_empty_description(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Description"):
        _create_statement(store, workgroups, description="")


def test_create_prepared_statement_rejects_too_long_description(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="Description"):
        _create_statement(
            store,
            workgroups,
            description="x" * (DESCRIPTION_STRING_MAX_LENGTH + 1),
        )


def test_create_prepared_statement_accepts_max_description(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    description = "x" * DESCRIPTION_STRING_MAX_LENGTH

    _create_statement(store, workgroups, description=description)

    assert store.get("stmt1", "primary").description == description


@pytest.mark.parametrize("workgroup", ["bad name!", "slash/name", "x" * 129])
def test_create_prepared_statement_rejects_invalid_workgroup_name(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
    workgroup: str,
) -> None:
    # Model WorkGroupName: [a-zA-Z0-9._-]{1,128}.
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        _create_statement(store, workgroups, workgroup=workgroup)


def test_create_prepared_statement_rejects_unknown_workgroup(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    # moto resolves the workgroup on create (Athena responses.py:283-284), so
    # a pattern-valid but unregistered name is a 400, not a silent store.
    with pytest.raises(
        InvalidRequestException, match="WorkGroup ghost_wg does not exist"
    ):
        _create_statement(store, workgroups, workgroup="ghost_wg")


def test_get_prepared_statement_rejects_invalid_workgroup_name(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        get_prepared_statement(
            store, {"StatementName": "stmt1", "WorkGroup": "bad name!"}
        )


@pytest.mark.parametrize("statement_name", ["1stmt", "has-hyphen"])
def test_get_prepared_statement_rejects_invalid_statement_name(
    store: PreparedStatementStore, statement_name: str
) -> None:
    with pytest.raises(InvalidRequestException, match="StatementName"):
        get_prepared_statement(
            store, {"StatementName": statement_name, "WorkGroup": "primary"}
        )


def test_update_prepared_statement_rejects_invalid_workgroup_name(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        update_prepared_statement(
            store,
            {
                "StatementName": "stmt1",
                "WorkGroup": "bad name!",
                "QueryStatement": "SELECT 1",
            },
        )


def test_update_prepared_statement_rejects_too_long_query_statement(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    _create_statement(store, workgroups, statement_name="upd_stmt")

    with pytest.raises(InvalidRequestException, match="QueryStatement"):
        update_prepared_statement(
            store,
            {
                "StatementName": "upd_stmt",
                "WorkGroup": "primary",
                "QueryStatement": "x" * (QUERY_STRING_MAX_LENGTH + 1),
            },
        )


def test_update_prepared_statement_rejects_empty_description(
    store: PreparedStatementStore,
    workgroups: WorkGroupStore,
) -> None:
    _create_statement(store, workgroups, statement_name="upd_stmt")

    with pytest.raises(InvalidRequestException, match="Description"):
        update_prepared_statement(
            store,
            {
                "StatementName": "upd_stmt",
                "WorkGroup": "primary",
                "QueryStatement": "SELECT 2",
                "Description": "",
            },
        )


def test_delete_prepared_statement_rejects_invalid_workgroup_name(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        delete_prepared_statement(
            store, {"StatementName": "stmt1", "WorkGroup": "bad name!"}
        )


@pytest.mark.parametrize("statement_name", ["1stmt", "has-hyphen"])
def test_delete_prepared_statement_rejects_invalid_statement_name(
    store: PreparedStatementStore, statement_name: str
) -> None:
    with pytest.raises(InvalidRequestException, match="StatementName"):
        delete_prepared_statement(
            store, {"StatementName": statement_name, "WorkGroup": "primary"}
        )


def test_batch_get_prepared_statement_rejects_invalid_workgroup_name(
    store: PreparedStatementStore,
) -> None:
    with pytest.raises(InvalidRequestException, match="WorkGroup"):
        batch_get_prepared_statement(
            store,
            {"PreparedStatementNames": ["stmt1"], "WorkGroup": "bad name!"},
        )
