"""Step definitions for the feast apply/materialize BDD feature.

Steps run the real `feast -c <repo> apply` command and the real
`LocalFeastMaterializer().apply` → `FeatureStore.materialize` loop
against a tmp copy of the checked-in `feature_repo/` — the seam the gap
register found exercised only through `FakeFeatureStore`. The copy keeps
registry/online-store writes off the real tree; feast itself is a
required dependency, not a fake.
"""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from nyc_taxi_demand_forecasting.features.feast_materialization import (
    LocalFeastMaterializer,
)
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/feast_apply.feature")

_REPO_PATH = Path(__file__).resolve().parents[2] / "feature_repo"


@dataclass
class FeastRun:
    """State shared between the given/when/then steps of a scenario."""

    repo_path: Path = Path()
    second_repo_path: Path = Path()
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
    _write_source_parquet(tmp_path)


@given(parsers.parse('a second copied repo whose view is named "{view_name}"'))
def _second_repo_copy(run: FeastRun, tmp_path: Path, view_name: str) -> None:
    # Arrange — same defs, different view name: the name registered on the
    # second store proves which repo's modules were bound during its load.
    # Both repos resolve the same `../data/processed/` sibling.
    run.second_repo_path = tmp_path / "feature_repo_b"
    shutil.copytree(
        _REPO_PATH,
        run.second_repo_path,
        ignore=shutil.ignore_patterns("__pycache__", "data"),
    )
    views_path = run.second_repo_path / "feature_views.py"
    views_path.write_text(
        views_path.read_text(encoding="utf-8").replace(
            'name="hourly_pickup_demand"', f'name="{view_name}"'
        ),
        encoding="utf-8",
    )


def _write_source_parquet(tmp_path: Path) -> None:
    # The frame matches `HourlyDemandFeatureBuilder.build_from_dataset`:
    # entity key + event timestamp + the view's schema columns. The
    # timestamp stays `datetime64[us]` like the real parquet — ns storage
    # reads back as duckdb TIMESTAMP_NS, which the materialize window
    # comparison rejects against its TIMESTAMPTZ bounds.
    source_dir = tmp_path / "data" / "processed"
    source_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "pickup_location_id": pd.Series([1], dtype="int64"),
            "event_timestamp": pd.Series(
                ["2023-01-01"], dtype="datetime64[us]"
            ),
            "pickup_count": pd.Series([3], dtype="int64"),
            "hour": pd.Series([8], dtype="int64"),
            "day_of_week": pd.Series([1], dtype="int64"),
            "is_weekend": pd.Series([False], dtype="bool"),
            "month": pd.Series([1], dtype="int64"),
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


@when("the materializer applies and materializes the copied repo")
def _apply_and_materialize(run: FeastRun) -> None:
    # Act — the in-process path `pipelines/features.py` runs: apply the
    # repo's defs, then materialize the parquet window into the online
    # store.
    from feast import FeatureStore

    LocalFeastMaterializer().apply(run.repo_path)
    store = FeatureStore(repo_path=str(run.repo_path))
    store.materialize(datetime(2023, 1, 1), datetime(2023, 1, 2))


@when("the materializer applies both copied repos")
def _apply_both(run: FeastRun) -> None:
    # Act — two applies in one process; the second must bind its own
    # repo's modules, not the first repo's stale entries.
    LocalFeastMaterializer().apply(run.repo_path)
    LocalFeastMaterializer().apply(run.second_repo_path)


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


@then(
    parsers.parse(
        'the online store serves "{expected}" pickups for location '
        '"{location_id}"'
    )
)
def _online_serves(run: FeastRun, expected: str, location_id: str) -> None:
    # Assert — the materialized window must answer an online read.
    from feast import FeatureStore

    frame = (
        FeatureStore(repo_path=str(run.repo_path))
        .get_online_features(
            features=["hourly_pickup_demand:pickup_count"],
            entity_rows=[{"pickup_location_id": int(location_id)}],
        )
        .to_df()
    )
    assert frame["pickup_count"].iloc[0] == int(expected)


@then(parsers.parse('the second registry lists only "{view_name}"'))
def _second_registry(run: FeastRun, view_name: str) -> None:
    # Assert — stale module bindings would register the first repo's view.
    from feast import FeatureStore

    store = FeatureStore(repo_path=str(run.second_repo_path))
    assert [view.name for view in store.list_feature_views()] == [view_name]


@then(parsers.parse('the first registry lists "{view_name}"'))
def _first_registry(run: FeastRun, view_name: str) -> None:
    # Assert
    from feast import FeatureStore

    store = FeatureStore(repo_path=str(run.repo_path))
    assert [view.name for view in store.list_feature_views()] == [view_name]
