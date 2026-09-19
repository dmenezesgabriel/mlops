"""App-level tests: POST / dispatch, health endpoint, 70-op error shape.

Every operation is out of scope while the dispatch table is empty, so each of
the 70 targets must answer with a shaped ``InvalidRequestException`` (400) that
botocore parses cleanly (PRD FR-17).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from athena_local.dispatch import operation_names
from athena_local.main import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


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
    "operation", sorted(operation_names()), ids=sorted(operation_names())
)
def test_every_operation_answers_shaped_error(
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
