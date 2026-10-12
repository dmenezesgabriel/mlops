"""Step definitions for the feast-apply BDD feature.

Steps run the real `feast -c <repo> apply` against a tmp copy of the
checked-in `feature_repo/` — the seam the gap register found had zero
execution coverage. The copy keeps the registry/online-store writes off
the real tree; feast itself is a required dependency, not a fake.
"""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/feast_apply.feature")

_REPO_PATH = Path(__file__).resolve().parents[2] / "feature_repo"


@dataclass
class FeastRun:
    """State shared between the given/when/then steps of a scenario."""

    repo_path: Path = Path()
    returncode: int | None = None
    output: str = ""


@pytest.fixture
def run() -> FeastRun:
    return FeastRun()


@given("a copy of the feature repo with its offline source parquet")
def _repo_copy(run: FeastRun, tmp_path: Path) -> None:
    # Arrange — `data/` holds local run artifacts when present, never
    # checked-in definitions.
    run.repo_path = tmp_path / "feature_repo"
    shutil.copytree(
        _REPO_PATH,
        run.repo_path,
        ignore=shutil.ignore_patterns("__pycache__", "data"),
    )
    # The FileSource in data_sources.py resolves
    # `feature_repo/../data/processed/` — a sibling of the repo dir.
    source_dir = tmp_path / "data" / "processed"
    source_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "pickup_location_id": pd.Series([1], dtype="int64"),
            "event_timestamp": pd.to_datetime(["2023-01-01"]),
            "pickup_count": pd.Series([3], dtype="int64"),
            "hour": pd.Series([8], dtype="int64"),
            "day_of_week": pd.Series([1], dtype="int64"),
            "is_weekend": pd.Series([False], dtype="bool"),
            "month": pd.Series([1], dtype="int64"),
            "next_hour_pickup_count": pd.Series([5], dtype="int64"),
        }
    ).to_parquet(source_dir / "hourly_demand_features.parquet", index=False)


@when("I run feast apply on the copied repo")
def _feast_apply(run: FeastRun) -> None:
    # Act — resolve the binary beside the interpreter so the gate's venv
    # does not depend on PATH.
    feast_binary = Path(sys.executable).parent / "feast"
    proc = subprocess.run(
        [str(feast_binary), "-c", str(run.repo_path), "apply"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    run.returncode = proc.returncode
    run.output = proc.stdout + proc.stderr


@then("the apply succeeds")
def _apply_succeeded(run: FeastRun) -> None:
    # Assert
    assert run.returncode == 0, run.output


@then(parsers.parse('the registry lists the "{name}" feature view'))
def _registry_lists_view(run: FeastRun, name: str) -> None:
    # Assert — read back through the real store, not apply's stdout.
    from feast import FeatureStore

    store = FeatureStore(repo_path=str(run.repo_path))
    assert name in [view.name for view in store.list_feature_views()]


@then(parsers.parse('the registry lists the "{name}" entity'))
def _registry_lists_entity(run: FeastRun, name: str) -> None:
    # Assert
    from feast import FeatureStore

    store = FeatureStore(repo_path=str(run.repo_path))
    assert name in [entity.name for entity in store.list_entities()]
