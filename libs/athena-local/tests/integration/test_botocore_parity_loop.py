"""70-op parity loop over real HTTP (real transport).

A real boto3 client serializes each model-valid stub request and parses our
JSON-1.1 response for every operation, exactly as the five consumers do. The
loop must complete every round-trip — a response botocore cannot parse, or a
round-trip that never reaches the wire, fails the test straight away — and
each outcome is then asserted against the operation's output shape or
declared error shapes with the ADR-0008 headers and statuses.

Runs against the in-process uvicorn server (no docker); point the client at
the compose ``athena`` :5001 service via ``ATHENA_LOCAL_TEST_ENDPOINT`` when
the stack is up, which pins the deployed service.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import boto3
import pytest
from athena_local.catalog_metadata import register_catalog_metadata_handlers
from athena_local.dispatch import implemented_operations, operation_names
from athena_local.main import (
    data_catalog_store,
    named_query_store,
    prepared_statement_store,
    reset_query_plane,
    workgroup_store,
)
from botocore.client import BaseClient, Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ParamValidationError,
)
from botocore.parsers import ResponseParserError
from tests._parity import (
    NOT_IMPLEMENTED_MARKER,
    assert_modeled_client_error,
    assert_success_body,
    client_methods,
    fast_fail_glue_proxy,
    stub_payload,
)
from tests.integration.conftest import LiveAthenaServer

ALL_OPERATIONS = sorted(operation_names())
TEST_ENDPOINT_ENV = "ATHENA_LOCAL_TEST_ENDPOINT"


@pytest.fixture(scope="module")
def parity_client() -> Iterator[BaseClient]:
    """A boto3 Athena client bound to the live server or the compose service."""
    endpoint_url = os.environ.get(TEST_ENDPOINT_ENV)
    server = None
    if endpoint_url is None:
        server = LiveAthenaServer()
        server.start()
        endpoint_url = server.endpoint_url
    workgroup_store.reset()
    named_query_store.reset()
    prepared_statement_store.reset()
    data_catalog_store.reset()
    register_catalog_metadata_handlers(
        data_catalog_store, fast_fail_glue_proxy()
    )
    reset_query_plane()
    client = boto3_client(endpoint_url)
    yield client
    workgroup_store.reset()
    named_query_store.reset()
    prepared_statement_store.reset()
    data_catalog_store.reset()
    register_catalog_metadata_handlers(data_catalog_store)
    reset_query_plane()
    if server is not None:
        server.stop()


def boto3_client(endpoint_url: str) -> BaseClient:
    # Retries are disabled so the loop asserts the FIRST response: a modeled
    # 500 (InternalServerException) would otherwise be retried as a transient
    # error and the assertion would inspect only the final attempt.
    return boto3.client(
        "athena",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            connect_timeout=3, read_timeout=10, retries={"max_attempts": 0}
        ),
    )


def _invoke(
    client: BaseClient, operation: str
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    """Serialize, send, and parse one request; ``(result, error_response)``.

    ``error_response`` is populated for any parsed ClientError; a success
    leaves it ``None``. Transport/protocol failures propagate to the caller,
    whose except clauses classify them.
    """
    method_name = client_methods()[operation]
    request = stub_payload(operation)
    method = getattr(client, method_name)
    try:
        return method(**request), None
    except ClientError as error:
        return None, error.response


@pytest.mark.parametrize("operation", ALL_OPERATIONS, ids=ALL_OPERATIONS)
def test_every_operation_round_trips_through_botocore(
    parity_client: BaseClient, operation: str
) -> None:
    try:
        result, error_response = _invoke(parity_client, operation)
    except ParamValidationError as error:
        pytest.fail(
            f"{operation}: request stub failed model validation: {error}"
        )
    except (BotoCoreError, ResponseParserError) as error:
        pytest.fail(
            f"{operation}: botocore could not complete the round-trip: "
            f"{type(error).__name__}: {error}"
        )

    if error_response is not None:
        assert_modeled_client_error(error_response, operation)
        message = error_response["Error"]["Message"]
        if operation in implemented_operations():
            assert NOT_IMPLEMENTED_MARKER not in message, (
                f"{operation} is implemented but answered the default "
                "not-yet-implemented error; the composition root lost its handler"
            )
        else:
            assert NOT_IMPLEMENTED_MARKER in message, (
                f"{operation} is unimplemented but did not answer "
                "the not-yet-implemented error"
            )
        return

    assert result is not None
    success_body = {
        key: value
        for key, value in result.items()
        if key != "ResponseMetadata"
    }
    assert_success_body(success_body, operation)
    metadata = result["ResponseMetadata"]
    assert metadata["HTTPStatusCode"] == 200, (
        f"{operation} success carried status {metadata['HTTPStatusCode']}"
    )
    assert (
        metadata["HTTPHeaders"]["content-type"] == "application/x-amz-json-1.1"
    ), f"{operation} success content type mismatch"
