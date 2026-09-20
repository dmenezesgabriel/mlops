"""Dispatch-table tests: 70-op registry from the canonical model + target rules.

The registry is loaded at runtime from the installed botocore Athena model
(public ``ServiceModel.operation_names`` API); the canonical-model BDD feature
already proves installed == vendored reference, so the registry is trustworthy
as long as it matches that model exactly and stays at 70 operations.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from athena_local.dispatch import (
    OPERATION_HANDLERS,
    WireResponse,
    dispatch,
    implemented_operations,
    operation_names,
    parse_body,
    resolve_operation,
)
from athena_local.errors import InvalidRequestException
from botocore.session import Session

ATHENA_SERVICE_NAME = "athena"


def test_operation_names_register_exactly_seventy_operations() -> None:
    assert len(operation_names()) == 70


def test_operation_names_match_installed_model_without_drift() -> None:
    model = Session().get_service_model(ATHENA_SERVICE_NAME)
    assert operation_names() == frozenset(model.operation_names)


def test_resolve_operation_uses_final_target_segment() -> None:
    assert (
        resolve_operation("AmazonAthena.ListEngineVersions")
        == "ListEngineVersions"
    )


def test_resolve_operation_ignores_non_canonical_prefix() -> None:
    # moto also splits on the final dot regardless of prefix
    # (research_repos/moto/moto/core/responses.py:462-464).
    assert resolve_operation("Athena_2017_05_18.ListQueryExecutions") == (
        "ListQueryExecutions"
    )


def test_resolve_operation_rejects_missing_target() -> None:
    with pytest.raises(InvalidRequestException, match="X-Amz-Target"):
        resolve_operation(None)


def test_resolve_operation_rejects_empty_target() -> None:
    with pytest.raises(InvalidRequestException, match="X-Amz-Target"):
        resolve_operation(" ")


def test_resolve_operation_rejects_unknown_operation() -> None:
    with pytest.raises(InvalidRequestException, match="DoesNotExist"):
        resolve_operation("AmazonAthena.DoesNotExist")


def test_dispatch_known_operation_names_its_own_target() -> None:
    error = asyncio.run(dispatch("AmazonAthena.ListQueryExecutions"))

    assert isinstance(error, InvalidRequestException)
    assert "ListQueryExecutions" in error.message


def test_dispatch_unknown_target_is_a_shaped_error_naming_the_segment() -> (
    None
):
    error = asyncio.run(dispatch("AmazonAthena.Nope"))

    assert isinstance(error, InvalidRequestException)
    assert "Nope" in error.message


def test_dispatch_missing_target_is_a_shaped_error() -> None:
    error = asyncio.run(dispatch(None))

    assert isinstance(error, InvalidRequestException)


def test_dispatch_executes_coroutine_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(
        payload: dict[str, object] | None,
    ) -> dict[str, object]:
        assert payload == {"Query": "SELECT 1"}
        return {"QueryExecutionId": "async-ok"}

    monkeypatch.setitem(OPERATION_HANDLERS, "StopQueryExecution", handler)

    response = asyncio.run(
        dispatch("AmazonAthena.StopQueryExecution", b'{"Query": "SELECT 1"}')
    )

    assert isinstance(response, WireResponse)
    assert json.loads(response.body) == {"QueryExecutionId": "async-ok"}


def test_dispatch_runs_sync_handlers_under_async_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        OPERATION_HANDLERS,
        "GetQueryExecution",
        lambda _payload: {"QueryExecution": {"QueryExecutionId": "sync-ok"}},
    )

    response = asyncio.run(dispatch("AmazonAthena.GetQueryExecution"))

    assert isinstance(response, WireResponse)
    assert json.loads(response.body) == {
        "QueryExecution": {"QueryExecutionId": "sync-ok"}
    }


def test_dispatch_async_handler_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(
        _payload: dict[str, object] | None,
    ) -> dict[str, object]:
        raise InvalidRequestException("async failure")

    monkeypatch.setitem(OPERATION_HANDLERS, "StopQueryExecution", handler)

    error = asyncio.run(dispatch("AmazonAthena.StopQueryExecution"))

    assert isinstance(error, InvalidRequestException)
    assert "async failure" in error.message


def test_parse_body_parses_json_object() -> None:
    assert parse_body(b'{"Name": "analytics"}') == {"Name": "analytics"}


def test_parse_body_returns_none_for_empty_body() -> None:
    assert parse_body(None) is None
    assert parse_body(b"") is None
    assert parse_body(b"   ") is None


def test_parse_body_raises_on_malformed_json() -> None:
    with pytest.raises(InvalidRequestException, match="body"):
        parse_body(b'{"Name": ')


def test_parse_body_raises_on_non_object_json() -> None:
    with pytest.raises(InvalidRequestException, match="object"):
        parse_body(b'["analytics"]')


def test_implemented_operations_is_derived_from_the_registry() -> None:
    assert isinstance(implemented_operations(), frozenset)
    assert implemented_operations() <= operation_names()
