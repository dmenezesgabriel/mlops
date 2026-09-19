# ruff: noqa: N818  (exception names are pinned to the Athena wire shapes, ADR-0008)
"""Athena JSON-1.1 error shapes and their wire serialization.

Parity contract (ADR-0008): body ``{"__type": "<shape>", "message": "<text>"}``
plus the ``X-Amzn-Errortype`` header and ``application/x-amz-json-1.1`` content
type. The canonical service-2.json carries no ``httpStatusCode`` metadata, so
the statuses are the AWS-documented codes for each exception (moto mirrors the
same set as ``JsonRESTError.code``).

Class names intentionally equal the AWS exception shape names, so a grep for
``InvalidRequestException`` finds the code that emits it.
"""

from __future__ import annotations

import json
import uuid
from typing import ClassVar

JSON_11_CONTENT_TYPE = "application/x-amz-json-1.1"


class AthenaError(Exception):
    """Base class for JSON-1.1 exceptions the emulator responds with."""

    shape_name: ClassVar[str] = ""
    status_code: ClassVar[int] = 0

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRequestException(AthenaError):
    shape_name = "InvalidRequestException"
    status_code = 400


class ResourceNotFoundException(AthenaError):  # noqa (protocol vocabulary, ADR-0008)
    shape_name = "ResourceNotFoundException"
    status_code = 404


class TooManyRequestsException(AthenaError):  # noqa (protocol vocabulary, ADR-0008)
    shape_name = "TooManyRequestsException"
    status_code = 429


class InternalServerException(AthenaError):  # noqa (protocol vocabulary, ADR-0008)
    shape_name = "InternalServerException"
    status_code = 500


def serialize_error(error: AthenaError) -> tuple[int, dict[str, str], str]:
    """Serialize ``error`` to ``(status, headers, json_body)``.

    ``x-amzn-requestid`` is a synthetic UUID so botocore's response metadata
    mirrors what real Athena returns.
    """
    body = json.dumps(
        {"__type": error.shape_name, "message": error.message},
        separators=(",", ":"),
    )
    headers = {
        "Content-Type": JSON_11_CONTENT_TYPE,
        "X-Amzn-Errortype": error.shape_name,
        "x-amzn-requestid": str(uuid.uuid4()),
    }
    return error.status_code, headers, body
