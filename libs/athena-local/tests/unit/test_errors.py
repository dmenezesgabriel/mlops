"""Wire-shape parity tests for the Athena JSON-1.1 error serializer.

Parity contract (ADR-0008): body ``{"__type": "<shape>", "message": "<text>"}``
plus ``X-Amzn-Errortype`` header, status per the AWS-documented HTTP status of
each exception. The canonical service model carries no ``httpStatusCode``
metadata, so the codes are pinned here as the read-only contract.
"""

from __future__ import annotations

import json

import pytest
from athena_local.errors import (
    AthenaError,
    InternalServerException,
    InvalidRequestException,
    MetadataException,
    ResourceNotFoundException,
    TooManyRequestsException,
    serialize_error,
)

PARITY_CASES: list[tuple[type[AthenaError], int]] = [
    (InvalidRequestException, 400),
    (ResourceNotFoundException, 404),
    (TooManyRequestsException, 429),
    (InternalServerException, 500),
    # Custom-metastore errors carry HTTP 400 per the AWS API reference (the
    # service model has no httpStatusCode metadata for this exception).
    (MetadataException, 400),
]


@pytest.mark.parametrize(
    ("error_class", "expected_status"),
    PARITY_CASES,
    ids=[
        "invalid-request",
        "resource-not-found",
        "too-many-requests",
        "internal-server",
        "metadata",
    ],
)
def test_serialize_error_matches_wire_contract(
    error_class: type[AthenaError], expected_status: int
) -> None:
    error = error_class("boom")
    status, headers, body = serialize_error(error)

    assert status == expected_status
    assert headers["X-Amzn-Errortype"] == error_class.shape_name
    assert headers["Content-Type"] == "application/x-amz-json-1.1"
    assert len(headers["x-amzn-requestid"]) == 36
    assert json.loads(body) == {
        "__type": error_class.shape_name,
        "message": "boom",
    }


def test_serialize_error_preserves_message() -> None:
    error = InvalidRequestException("Invalid workgroup name: analytics")
    _, _, body = serialize_error(error)

    assert json.loads(body)["message"] == "Invalid workgroup name: analytics"
