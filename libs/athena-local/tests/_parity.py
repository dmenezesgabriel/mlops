"""70-op parity loop helpers (CS-1): model-inflated stubs and wire assertions.

Stub request bodies are inflated from the canonical Athena model (required
members only, validated with botocore's ``validate_parameters``) so the loop
never sends a request the model rejects. Responses are asserted against each
operation's output shape (success: declare only model members) and its
declared error shape names (error: ``__type``/``X-Amzn-Errortype``/status
agree with the ADR-0008 vocabulary).
"""

from __future__ import annotations

import os
from functools import cache, lru_cache

import boto3
from athena_local.data_catalog_state import AWS_DATA_CATALOG_NAME
from athena_local.errors import (
    JSON_11_CONTENT_TYPE,
    AthenaError,
)
from athena_local.glue_proxy import GlueProxy
from botocore.client import Config
from botocore.model import OperationModel, ServiceModel, Shape
from botocore.session import Session
from botocore.validate import validate_parameters

# The status code each error shape is serialized with (ADR-0008). Derived from
# the emulator's own exceptions so the loop guards drift in the code, not in a
# copy of the mapping.
ERROR_STATUS_BY_SHAPE: dict[str, int] = {
    klass.shape_name: klass.status_code
    for klass in AthenaError.__subclasses__()
}

NOT_IMPLEMENTED_MARKER = "not yet implemented"


# Semantically meaningful stubs for operations whose bare required-member
# inflation would stop short of the boundary worth exercising: the four
# catalog-introspection reads name the seeded GLUE catalog so the request
# reaches the Glue proxy — whose transport failure (moto down) is itself a
# JSON-1.1 error shape (InternalServerException 500) the loop must pin.
SEMANTIC_STUBS: dict[str, dict[str, object]] = {
    "GetDatabase": {
        "CatalogName": AWS_DATA_CATALOG_NAME,
        "DatabaseName": "missing",
    },
    "ListDatabases": {"CatalogName": AWS_DATA_CATALOG_NAME},
    "GetTableMetadata": {
        "CatalogName": AWS_DATA_CATALOG_NAME,
        "DatabaseName": "missing",
        "TableName": "missing",
    },
    "ListTableMetadata": {
        "CatalogName": AWS_DATA_CATALOG_NAME,
        "DatabaseName": "missing",
    },
}


@lru_cache(maxsize=1)
def service_model() -> ServiceModel:
    """The canonical Athena service model installed with botocore.

    Cached: the loop calls it once per operation per assertion, and building a
    fresh Session and re-parsing service-2.json every time dominated the suite
    (CS-1 timing budget).
    """
    return Session().get_service_model("athena")


def fast_fail_glue_proxy() -> GlueProxy:
    """A Glue proxy that fails fast instead of retrying a down moto.

    The parity loop binds catalog handlers to this proxy so the four
    catalog-introspection reads reach the Glue boundary quickly in either
    direction: a down moto answers the shaped InternalServerException within
    one attempt, a running moto (compose, ``ATHENA_MOTO_ENDPOINT_URL``)
    serves real data.
    """
    session = Session()
    client = session.create_client(
        "glue",
        endpoint_url=(
            os.getenv("ATHENA_MOTO_ENDPOINT_URL") or "http://127.0.0.1:5000"
        ),
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            connect_timeout=2, read_timeout=5, retries={"max_attempts": 0}
        ),
    )
    return GlueProxy(client)


@cache
def operation_model(op_name: str) -> OperationModel:
    return service_model().operation_model(op_name)


def error_shape_names(op_name: str) -> set[str]:
    """The error shapes the canonical model declares for ``op_name``."""
    return {shape.name for shape in operation_model(op_name).error_shapes}


def stub_payload(op_name: str) -> dict[str, object]:
    """Inflate a model-valid request body for an operation.

    The body covers exactly the operation's required members. It is passed
    through botocore's ``validate_parameters`` so an inflater bug or a model
    change fails here with the offender, not later as a server mystery.
    """
    input_shape = operation_model(op_name).input_shape
    if input_shape is None:
        return {}
    semantic = SEMANTIC_STUBS.get(op_name)
    payload = (
        semantic if semantic is not None else inflate_structure(input_shape)
    )
    validate_parameters(payload, input_shape)
    return payload


def inflate_structure(shape: Shape) -> dict[str, object]:
    return {
        name: inflate_member(shape.members[name])
        for name in shape.required_members
    }


def inflate_member(member: Shape) -> object:
    """A minimal value for ``member`` that satisfies the model's constraints."""
    if member.type_name == "string":
        if member.enum:
            return member.enum[0]
        minimum = member.metadata.get("min")
        return (
            "x" * minimum if isinstance(minimum, int) and minimum > 1 else "x"
        )
    if member.type_name in ("integer", "long"):
        minimum = member.metadata.get("min")
        return minimum if isinstance(minimum, int) else 1
    if member.type_name == "boolean":
        return True
    if member.type_name == "structure":
        return inflate_structure(member)
    if member.type_name == "list":
        return [inflate_member(member.member)]
    if member.type_name == "map":
        return {"k": inflate_member(member.value)}
    raise ValueError(
        f"Inflater has no stub for {member.type_name} shape {member.name}"
    )


def assert_success_body(body: dict[str, object], op_name: str) -> None:
    """A 200 response may only declare members of the operation's output shape."""
    output_shape = operation_model(op_name).output_shape
    output_members = set(output_shape.members) if output_shape else set()
    extra = set(body) - output_members
    assert not extra, (
        f"{op_name} response declares members the model does not: {sorted(extra)}"
    )


def assert_shaped_error(
    status_code: int,
    headers: dict[str, str],
    body: dict[str, object],
    op_name: str,
) -> None:
    """The JSON-1.1 error contract (ADR-0008): __type, errortype, status."""
    error_type = body.get("__type")
    assert isinstance(error_type, str), (
        f"{op_name} error lacks a __type string"
    )
    assert error_type in error_shape_names(op_name), (
        f"{op_name} answered undeclared error shape {error_type}; "
        f"model declares {error_shape_names(op_name)}"
    )
    header_value = headers.get("X-Amzn-Errortype")
    assert header_value == error_type, (
        f"{op_name} X-Amzn-Errortype {header_value!r} != __type {error_type!r}"
    )
    assert headers.get("Content-Type") == JSON_11_CONTENT_TYPE, (
        f"{op_name} error content type is not {JSON_11_CONTENT_TYPE}"
    )
    assert isinstance(body.get("message"), str) and body["message"], (
        f"{op_name} error carries no message"
    )
    expected_status = ERROR_STATUS_BY_SHAPE[error_type]
    assert status_code == expected_status, (
        f"{op_name} answered status {status_code} for shape {error_type}; "
        f"expected {expected_status}"
    )


@lru_cache(maxsize=1)
def client_methods() -> dict[str, str]:
    """Map each operation to the boto3 client method a consumer would call."""
    client = boto3.client(
        "athena",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return {
        api_name: python_name
        for python_name, api_name in client.meta.method_to_api_mapping.items()
    }


def assert_modeled_client_error(
    response: dict[str, object], op_name: str
) -> None:
    """A parsed ClientError agrees with the model and the emulator's statuses."""
    error = response["Error"]
    assert isinstance(error, dict)
    code = error.get("Code")
    assert isinstance(code, str), f"{op_name} error has no Code string"
    assert code in error_shape_names(op_name), (
        f"{op_name} parsed undeclared error code {code}; "
        f"model declares {error_shape_names(op_name)}"
    )
    metadata = response["ResponseMetadata"]
    assert isinstance(metadata, dict)
    status_code = metadata.get("HTTPStatusCode")
    assert status_code == ERROR_STATUS_BY_SHAPE[code], (
        f"{op_name} answered status {status_code} for shape {code}; "
        f"expected {ERROR_STATUS_BY_SHAPE[code]}"
    )
    headers = metadata.get("HTTPHeaders")
    assert isinstance(headers, dict)
    assert headers.get("content-type") == JSON_11_CONTENT_TYPE, (
        f"{op_name} error content type is not {JSON_11_CONTENT_TYPE}"
    )
    assert headers.get("x-amzn-errortype") == code, (
        f"{op_name} errortype header does not match parsed code {code}"
    )
