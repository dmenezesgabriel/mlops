"""Step definitions for the canonical-model BDD feature.

The assertions encode the measured agreement between the two frozen
references: the vendored Athena model under ``research_repos/aws-cli`` and
the botocore model installed in the environment (byte-identical, both
241,641 bytes), plus moto's dispatch rule — resolve the operation as the
segment after the final dot of ``X-Amz-Target``
(``research_repos/moto/moto/core/responses.py:462-464``). botocore builds
that header as ``f"{metadata.targetPrefix}.{operation}"``
(installed botocore ``serialize.py:423-425``); measured on the wire a real
boto3 client sends ``X-Amz-Target: AmazonAthena.StartQueryExecution``.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import cast

import pytest
from pytest_bdd import given, scenarios, then, when

scenarios("canonical_model.feature")

REPO_ROOT = Path(__file__).resolve().parents[4]
REFERENCE_MODEL = (
    REPO_ROOT
    / "research_repos"
    / "aws-cli"
    / "awscli"
    / "botocore"
    / "data"
    / "athena"
    / "2017-05-18"
    / "service-2.json"
)


@lru_cache(maxsize=1)
def _parse_reference_model() -> dict[str, object]:
    return cast(dict[str, object], json.loads(REFERENCE_MODEL.read_text()))


@lru_cache(maxsize=1)
def _installed_botocore_model_bytes() -> bytes:
    spec = importlib.util.find_spec("botocore")
    if spec is None or spec.origin is None:
        raise AssertionError("botocore must be installed to compare models")
    package_dir = Path(spec.origin).parent
    model_gz = (
        package_dir / "data" / "athena" / "2017-05-18" / "service-2.json.gz"
    )
    return gzip.decompress(model_gz.read_bytes())


@dataclass
class ModelComparison:
    """Holds the byte-comparison result passed between the when and then steps."""

    identical: bool = False


@pytest.fixture
def comparison() -> ModelComparison:
    return ModelComparison()


@pytest.fixture
def canonical_model() -> dict[str, object]:
    return _parse_reference_model()


@pytest.fixture
def installed_model_bytes() -> bytes:
    return _installed_botocore_model_bytes()


@given("the canonical Athena service-2.json")
def _load_canonical_model(canonical_model: dict[str, object]) -> None:
    assert "operations" in canonical_model


@given("a decompressed copy of the installed botocore Athena model")
def _load_installed_model(installed_model_bytes: bytes) -> None:
    assert installed_model_bytes


@when("the installed model is compared byte-for-byte with the reference")
def compare_installed_with_reference(
    installed_model_bytes: bytes, comparison: ModelComparison
) -> None:
    comparison.identical = (
        installed_model_bytes == REFERENCE_MODEL.read_bytes()
    )


@then("the two models are identical")
def assert_models_identical(comparison: ModelComparison) -> None:
    assert comparison.identical


@then("the model declares 70 operations")
def assert_seventy_operations(canonical_model: dict[str, object]) -> None:
    operations = cast(dict[str, object], canonical_model["operations"])
    assert len(operations) == 70


@then("the model uses the json protocol with jsonVersion 1.1")
def assert_json_protocol(canonical_model: dict[str, object]) -> None:
    metadata = cast(dict[str, object], canonical_model["metadata"])
    assert metadata["protocol"] == "json"
    assert metadata["jsonVersion"] == "1.1"


@then("the metadata targets the athena endpoint prefix")
def assert_endpoint_prefix(canonical_model: dict[str, object]) -> None:
    metadata = cast(dict[str, object], canonical_model["metadata"])
    assert metadata["endpointPrefix"] == "athena"
    assert metadata["targetPrefix"] == "AmazonAthena"


@then(
    "every operation's X-Amz-Target ends with the operation name after the final dot"
)
def assert_target_suffix_matches_operation(
    canonical_model: dict[str, object],
) -> None:
    metadata = cast(dict[str, object], canonical_model["metadata"])
    target_prefix = cast(str, metadata["targetPrefix"])
    operations = cast(dict[str, object], canonical_model["operations"])
    for operation in operations:
        target = f"{target_prefix}.{operation}"
        # moto resolves the action as the segment after the final dot.
        assert target.split(".")[-1] == operation
