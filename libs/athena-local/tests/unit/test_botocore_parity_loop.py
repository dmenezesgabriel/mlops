"""70-op parity loop at the dispatch level (model-valid stubs).

Every operation declared by the canonical model answers a model-valid body
with a JSON-1.1-shaped outcome: either a success whose keys are declared by
the operation's output shape, or an error whose ``__type``, errortype header,
and status belong to the operation's declared error shapes. Where test_main
probes a handful of flows, this loop is exhaustive and drives every op with a
real (inflated) body instead of an empty one.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from athena_local.catalog_metadata import register_catalog_metadata_handlers
from athena_local.dispatch import implemented_operations, operation_names
from athena_local.glue_proxy import GlueProxy
from athena_local.main import (
    app,
    data_catalog_store,
    named_query_store,
    prepared_statement_store,
    reset_query_plane,
    workgroup_store,
)
from fastapi.testclient import TestClient
from tests._parity import (
    NOT_IMPLEMENTED_MARKER,
    assert_shaped_error,
    assert_success_body,
    fast_fail_glue_proxy,
    stub_payload,
)

ALL_OPERATIONS = sorted(operation_names())


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    # One TestClient for the whole module: cases stay independent because the
    # autouse reset fixture restores every store around each case. Starting a
    # TestClient per case (210 of them) dominated the dispatch-layer run time.
    with TestClient(app) as test_client:
        yield test_client
    # Leave the composition root on the default env-bound Glue proxy (ADR-0002)
    # for whatever module runs next.
    reset_query_plane()
    register_catalog_metadata_handlers(data_catalog_store)


@pytest.fixture(scope="module")
def fast_glue_proxy() -> GlueProxy:
    # Single fail-fast Glue client shared by every rebind so a down moto
    # answers the shaped InternalServerException in one attempt instead of
    # botocore's default retry backoff.
    return fast_fail_glue_proxy()


@pytest.fixture(autouse=True)
def reset_emulator_state(fast_glue_proxy: GlueProxy) -> Iterator[None]:
    # The app owns module-level stores that survive TestClient restarts
    # (ADR-0003), so reset them before each case and rebind the four
    # catalog-introspection reads to the fail-fast proxy.
    workgroup_store.reset()
    named_query_store.reset()
    prepared_statement_store.reset()
    data_catalog_store.reset()
    register_catalog_metadata_handlers(data_catalog_store, fast_glue_proxy)
    reset_query_plane()
    yield


@pytest.mark.parametrize("operation", ALL_OPERATIONS, ids=ALL_OPERATIONS)
def test_stub_payloads_validate_against_the_model(operation: str) -> None:
    # The stubs are THE loop's request material; validate_parameters inside
    # stub_payload must accept them or the response assertions below would be
    # testing a request the canonical model rejects.
    stub_payload(operation)


@pytest.mark.parametrize("operation", ALL_OPERATIONS, ids=ALL_OPERATIONS)
def test_every_operation_answers_a_model_shaped_response(
    client: TestClient, operation: str
) -> None:
    response = client.post(
        "/",
        headers={"X-Amz-Target": f"AmazonAthena.{operation}"},
        json=stub_payload(operation),
    )

    if response.status_code == 200:
        assert_success_body(response.json(), operation)
    else:
        assert_shaped_error(
            response.status_code, response.headers, response.json(), operation
        )


@pytest.mark.parametrize(
    "operation",
    sorted(operation_names() - implemented_operations()),
    ids=sorted(operation_names() - implemented_operations()),
)
def test_unimplemented_operation_answers_not_implemented(
    client: TestClient, operation: str
) -> None:
    response = client.post(
        "/",
        headers={"X-Amz-Target": f"AmazonAthena.{operation}"},
        json=stub_payload(operation),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["__type"] == "InvalidRequestException"
    assert NOT_IMPLEMENTED_MARKER in body["message"]


@pytest.mark.parametrize(
    "operation",
    sorted(implemented_operations()),
    ids=sorted(implemented_operations()),
)
def test_implemented_operation_never_answers_not_implemented(
    client: TestClient, operation: str
) -> None:
    # A bound handler that still answers the registry's default would mean the
    # composition root failed to register it (main.py wiring regressions).
    response = client.post(
        "/",
        headers={"X-Amz-Target": f"AmazonAthena.{operation}"},
        json=stub_payload(operation),
    )

    if response.status_code != 200:
        assert NOT_IMPLEMENTED_MARKER not in response.json()["message"]
