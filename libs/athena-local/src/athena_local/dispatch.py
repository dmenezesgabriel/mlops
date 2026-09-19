"""X-Amz-Target dispatch for the Athena JSON-1.1 protocol (ADR-0008).

The operation registry is read once from the installed botocore Athena model
via its public ``ServiceModel.operation_names`` API; the canonical-model BDD
feature proves the installed model is byte-identical to the vendored
reference, so no static copy of the 70 op names lives in this repo.

While the handler registry is empty every target answers with a shaped
``InvalidRequestException``: unknown targets name the offending segment,
known-but-unimplemented operations state that they are not yet implemented.
"""

from __future__ import annotations

from functools import lru_cache
from typing import cast

from botocore.session import Session

from athena_local.errors import AthenaError, InvalidRequestException

ATHENA_SERVICE_NAME = "athena"


@lru_cache(maxsize=1)
def operation_names() -> frozenset[str]:
    """The 70 operation names declared by the canonical Athena model."""
    model = Session().get_service_model(ATHENA_SERVICE_NAME)
    # botocore declares operation_names as a CachedProperty descriptor, so
    # pyright cannot infer the list type behind it.
    return frozenset(cast(list[str], model.operation_names))


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


def dispatch(target_header: str | None) -> AthenaError:
    """Resolve the target and return the response error (empty dispatch).

    Every operation is out of scope while no handlers are registered, so the
    result is always a shaped InvalidRequestException naming the operation.
    """
    try:
        operation = resolve_operation(target_header)
    except InvalidRequestException as error:
        return error
    return InvalidRequestException(
        f"Operation {operation} is not yet implemented by the emulator"
    )
