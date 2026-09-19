"""X-Amz-Target dispatch for the Athena JSON-1.1 protocol (ADR-0008).

The operation registry is read once from the installed botocore Athena model
via its public ``ServiceModel.operation_names`` API; the canonical-model BDD
feature proves the installed model is byte-identical to the vendored
reference, so no static copy of the 70 op names lives in this repo.

Operations without a registered handler answer with a shaped
``InvalidRequestException``: unknown targets name the offending segment,
known-but-unimplemented operations state that they are not yet implemented.
Handlers register themselves via :func:`register_handler`; an implemented
operation answers with a JSON-1.1 success response or raises an
``AthenaError`` that ``dispatch`` serializes.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import cast

from botocore.session import Session

from athena_local.errors import (
    JSON_11_CONTENT_TYPE,
    AthenaError,
    InvalidRequestException,
)

ATHENA_SERVICE_NAME = "athena"

# A handler receives the parsed JSON request object (or None for an empty
# body) and returns the operation's output object for success serialization.
OperationHandler = Callable[[dict[str, object] | None], dict[str, object]]

OPERATION_HANDLERS: dict[str, OperationHandler] = {}


@lru_cache(maxsize=1)
def operation_names() -> frozenset[str]:
    """The 70 operation names declared by the canonical Athena model."""
    model = Session().get_service_model(ATHENA_SERVICE_NAME)
    # botocore declares operation_names as a CachedProperty descriptor, so
    # pyright cannot infer the list type behind it.
    return frozenset(cast(list[str], model.operation_names))


def register_handler(operation: str, handler: OperationHandler) -> None:
    """Bind ``handler`` to an operation name declared by the canonical model."""
    if operation not in operation_names():
        raise ValueError(
            f"Cannot register a handler for unknown Athena operation {operation}"
        )
    OPERATION_HANDLERS[operation] = handler


def implemented_operations() -> frozenset[str]:
    """The operation names with a registered handler."""
    return frozenset(OPERATION_HANDLERS)


def resolve_operation(target_header: str | None) -> str:
    """Map an X-Amz-Target header to its operation name.

    The operation is the segment after the final dot, whatever the prefix
    (moto ``core/responses.py:462-464``). Raises InvalidRequestException for a
    missing, empty, or unknown target.
    """
    if not target_header or not target_header.strip():
        raise InvalidRequestException("Missing X-Amz-Target header")
    operation = target_header.split(".")[-1]
    if operation not in operation_names():
        raise InvalidRequestException(f"Unknown Athena operation: {operation}")
    return operation


@dataclass(frozen=True)
class WireResponse:
    """A JSON-1.1 success response built outside the FastAPI layer."""

    status_code: int
    headers: dict[str, str]
    body: str


def parse_body(body: bytes | None) -> dict[str, object] | None:
    """Parse the request body into a dict, or None for an empty body.

    The Content-Type header is not trusted for parsing: botocore sends
    ``application/x-amz-json-1.1`` with an optional charset, and the request
    serialization is defined by the service model regardless of the header
    variant (moto ``core/responses.py:468``).
    """
    if body is None or not body.strip():
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as error:
        raise InvalidRequestException(
            f"Malformed JSON request body: {error}"
        ) from error
    if not isinstance(parsed, dict):
        raise InvalidRequestException(
            f"Request body must be a JSON object, got {type(parsed).__name__}"
        )
    return cast(dict[str, object], parsed)


def serialize_success(payload: dict[str, object]) -> WireResponse:
    """Serialize an operation's output object into a JSON-1.1 response."""
    body = json.dumps(payload, separators=(",", ":"))
    headers = {
        "Content-Type": JSON_11_CONTENT_TYPE,
        "x-amzn-requestid": str(uuid.uuid4()),
    }
    return WireResponse(status_code=200, headers=headers, body=body)


def dispatch(
    target_header: str | None, body: bytes | None = None
) -> AthenaError | WireResponse:
    """Resolve the target, run its handler, and return the wire outcome.

    Unknown or unimplemented targets return a shaped
    ``InvalidRequestException``; handler ``AthenaError``s propagate unchanged;
    a handler's output object is serialized as a successful JSON-1.1 response.
    """
    try:
        operation = resolve_operation(target_header)
    except InvalidRequestException as error:
        return error
    handler = OPERATION_HANDLERS.get(operation)
    if handler is None:
        return InvalidRequestException(
            f"Operation {operation} is not yet implemented by the emulator"
        )
    try:
        result = handler(parse_body(body))
    except AthenaError as error:
        return error
    return serialize_success(result)
