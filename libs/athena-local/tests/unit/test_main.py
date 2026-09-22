"""App-level tests: POST / dispatch, health endpoint, shaped-error contract.

Every operation without a registered handler must answer with a shaped
``InvalidRequestException`` (400) that botocore parses cleanly (PRD FR-17);
implemented operations answer with JSON-1.1 success responses (MD-1: the five
workgroup operations). The composition root (PC-6) also owns the six
query-plane operations, whose wiring is asserted here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from athena_local.dispatch import implemented_operations, operation_names
from athena_local.executions import ExecutionStore
from athena_local.main import (
    TRINO_URL_ENV,
    app,
    build_query_executor,
    execution_store,
    reset_query_plane,
    workgroup_store,
)
from fastapi.testclient import TestClient

QUERY_PLANE_OPERATIONS = {
    "StartQueryExecution",
    "StopQueryExecution",
    "GetQueryExecution",
    "BatchGetQueryExecution",
    "GetQueryResults",
    "GetQueryRuntimeStatistics",
}


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_workgroups() -> Iterator[None]:
    workgroup_store.reset()
    yield
    workgroup_store.reset()


def test_health_endpoint_reports_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_is_not_part_of_the_wire_protocol(
    client: TestClient,
) -> None:
    response = client.post("/health")

    assert response.status_code == 405


@pytest.mark.parametrize(
    "operation",
    sorted(operation_names() - implemented_operations()),
    ids=sorted(operation_names() - implemented_operations()),
)
def test_every_unimplemented_operation_answers_shaped_error(
    client: TestClient, operation: str
) -> None:
    response = client.post(
        "/", headers={"X-Amz-Target": f"AmazonAthena.{operation}"}
    )

    assert response.status_code == 400
    assert response.headers["X-Amzn-Errortype"] == "InvalidRequestException"
    assert response.json()["__type"] == "InvalidRequestException"
    assert operation in response.json()["message"]


def test_unknown_target_is_a_shaped_error(client: TestClient) -> None:
    response = client.post("/", headers={"X-Amz-Target": "AmazonAthena.Nope"})

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidRequestException"
    assert "Nope" in response.json()["message"]


def test_missing_target_is_a_shaped_error(client: TestClient) -> None:
    response = client.post("/")

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidRequestException"
    assert "X-Amz-Target" in response.json()["message"]


def test_error_content_type_is_json_11(client: TestClient) -> None:
    response = client.post(
        "/", headers={"X-Amz-Target": "AmazonAthena.ListEngineVersions"}
    )

    assert response.headers["Content-Type"] == "application/x-amz-json-1.1"


def test_create_work_group_returns_json11_empty_object(
    client: TestClient,
) -> None:
    create = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={
            "Name": "analytics",
            "Configuration": {"EnforceWorkGroupConfiguration": True},
        },
    )
    assert create.status_code == 200
    assert create.headers["Content-Type"] == "application/x-amz-json-1.1"
    assert create.json() == {}


def test_get_work_group_returns_stored_configuration(
    client: TestClient,
) -> None:
    client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={
            "Name": "analytics",
            "Configuration": {"EnforceWorkGroupConfiguration": True},
        },
    )
    get = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.GetWorkGroup"},
        json={"WorkGroup": "analytics"},
    )
    assert get.status_code == 200
    assert get.json()["WorkGroup"]["Name"] == "analytics"
    assert (
        get.json()["WorkGroup"]["Configuration"][
            "EnforceWorkGroupConfiguration"
        ]
        is True
    )


def test_list_work_groups_returns_primary_and_created(
    client: TestClient,
) -> None:
    client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={"Name": "analytics"},
    )
    listing = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.ListWorkGroups"},
        json={},
    )
    assert [item["Name"] for item in listing.json()["WorkGroups"]] == [
        "primary",
        "analytics",
    ]


def test_update_work_group_modifies_state(client: TestClient) -> None:
    client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={"Name": "analytics"},
    )
    update = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.UpdateWorkGroup"},
        json={"WorkGroup": "analytics", "State": "DISABLED"},
    )
    assert update.status_code == 200
    assert update.json() == {}
    get = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.GetWorkGroup"},
        json={"WorkGroup": "analytics"},
    )
    assert get.json()["WorkGroup"]["State"] == "DISABLED"


def test_delete_work_group_removes_from_registry(
    client: TestClient,
) -> None:
    client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={"Name": "analytics"},
    )
    delete = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.DeleteWorkGroup"},
        json={"WorkGroup": "analytics"},
    )
    assert delete.status_code == 200
    assert delete.json() == {}
    listing = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.ListWorkGroups"},
        json={},
    )
    assert [item["Name"] for item in listing.json()["WorkGroups"]] == [
        "primary"
    ]


def test_create_work_group_accepts_charset_content_type(
    client: TestClient,
) -> None:
    response = client.post(
        "/",
        headers={
            "X-Amz-Target": "AmazonAthena.CreateWorkGroup",
            "Content-Type": "application/x-amz-json-1.1; charset=utf-8",
        },
        content=b'{"Name": "analytics"}',
    )

    assert response.status_code == 200


def test_create_work_group_parses_without_content_type(
    client: TestClient,
) -> None:
    response = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        content=b'{"Name": "analytics"}',
    )

    assert response.status_code == 200


def test_create_work_group_duplicate_is_shaped_400(client: TestClient) -> None:
    client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={"Name": "analytics"},
    )

    response = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.CreateWorkGroup"},
        json={"Name": "analytics"},
    )

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidRequestException"
    assert "analytics" in response.json()["message"]


def test_get_missing_workgroup_is_shaped_400(client: TestClient) -> None:
    response = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.GetWorkGroup"},
        json={"WorkGroup": "missing"},
    )

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidRequestException"
    assert "missing" in response.json()["message"]


def test_delete_primary_is_shaped_400(client: TestClient) -> None:
    response = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.DeleteWorkGroup"},
        json={"WorkGroup": "primary"},
    )

    assert response.status_code == 400
    assert response.json()["__type"] == "InvalidRequestException"
    assert "primary" in response.json()["message"]


def test_query_plane_operations_are_wired_by_the_composition_root(
    client: TestClient,
) -> None:
    response = client.post(
        "/",
        headers={"X-Amz-Target": "AmazonAthena.GetQueryExecution"},
        json={"QueryExecutionId": "missing-id"},
    )

    # Routed to the execution store's lookup ("does not exist"), not to the
    # "operation not yet implemented" answer (PC-6).
    assert response.status_code == 400
    assert "does not exist" in response.json()["message"]


def test_composition_root_registers_all_query_plane_operations() -> None:
    assert QUERY_PLANE_OPERATIONS <= implemented_operations()


def test_build_query_executor_reads_endpoints_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TRINO_URL_ENV, "http://trino:9999")
    monkeypatch.setenv("ATHENA_MOTO_ENDPOINT_URL", "http://moto:9998")

    executor = build_query_executor(ExecutionStore())

    assert executor._client._statement_url == "http://trino:9999/v1/statement"
    assert executor._writer._s3._client.meta.endpoint_url == "http://moto:9998"


def test_build_query_executor_uses_compose_default_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(TRINO_URL_ENV, raising=False)
    monkeypatch.delenv("ATHENA_MOTO_ENDPOINT_URL", raising=False)

    executor = build_query_executor(ExecutionStore())

    assert (
        executor._client._statement_url == "http://localhost:8080/v1/statement"
    )
    assert (
        executor._writer._s3._client.meta.endpoint_url
        == "http://127.0.0.1:5000"
    )


def test_reset_query_plane_clears_executions_and_rebinds_handlers() -> None:
    execution_store.create(query="SELECT 1", workgroup="primary")

    reset_query_plane()

    assert execution_store.by_id == {}
    assert QUERY_PLANE_OPERATIONS <= implemented_operations()
