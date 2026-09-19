"""Dispatch-table tests: 70-op registry from the canonical model + target rules.

The registry is loaded at runtime from the installed botocore Athena model
(public ``ServiceModel.operation_names`` API); the canonical-model BDD feature
already proves installed == vendored reference, so the registry is trustworthy
as long as it matches that model exactly and stays at 70 operations.
"""

from __future__ import annotations

import pytest
from athena_local.dispatch import dispatch, operation_names, resolve_operation
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
    error = dispatch("AmazonAthena.ListQueryExecutions")

    assert isinstance(error, InvalidRequestException)
    assert "ListQueryExecutions" in error.message


def test_dispatch_unknown_target_is_a_shaped_error_naming_the_segment() -> (
    None
):
    error = dispatch("AmazonAthena.Nope")

    assert isinstance(error, InvalidRequestException)
    assert "Nope" in error.message


def test_dispatch_missing_target_is_a_shaped_error() -> None:
    error = dispatch(None)

    assert isinstance(error, InvalidRequestException)
