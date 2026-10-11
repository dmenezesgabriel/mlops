import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import ml_specialization.inference.api as api
import pandas as pd
from ml_specialization.features.hourly_demand import (
    ENTITY_COLUMNS,
    FEATURE_COLUMNS,
    FEATURE_REFS,
    FEATURE_VIEW_NAME,
    load_entity_df,
)
from ml_specialization.inference import batch_predict

# The feast repo defs cannot import this package, so the schema lockstep is
# pinned here: load the repo's definition modules by file path like the
# materializer does.
_REPO_PATH = Path(__file__).resolve().parents[3] / "feature_repo"
_REPO_DEFINITION_MODULES = ("data_sources", "entities", "feature_views")


def test_feature_refs_are_view_qualified_feature_columns() -> None:
    # Assert — every consumer must request exactly this ref set.
    assert FEATURE_REFS == (
        "hourly_pickup_demand:pickup_count",
        "hourly_pickup_demand:hour",
        "hourly_pickup_demand:day_of_week",
        "hourly_pickup_demand:is_weekend",
        "hourly_pickup_demand:month",
    )


def test_serving_surfaces_import_the_contract() -> None:
    # Assert — api/batch_predict bind the contract module's constants, not
    # private literal copies that can drift apart.
    assert api.FEATURE_COLUMNS is FEATURE_COLUMNS
    assert api.FEATURE_REFS is FEATURE_REFS
    assert batch_predict.FEATURE_COLUMNS is FEATURE_COLUMNS


def test_repo_feature_view_schema_matches_feature_columns() -> None:
    # A feature-set change must fail loudly in one place.
    # Act
    modules = _load_repo_modules(_REPO_PATH)
    view = modules["feature_views"].hourly_pickup_demand_view

    # Assert — feast reorders schema fields internally, so compare the set.
    assert view.name == FEATURE_VIEW_NAME
    assert {field.name for field in view.schema} == set(FEATURE_COLUMNS)
    assert modules["entities"].pickup_location.join_key == ENTITY_COLUMNS[0]


def test_load_entity_df_synthesizes_event_timestamp(
    tmp_path: Path,
) -> None:
    # Arrange — a supervised dataset carrying pickup_hour but no timestamp.
    dataset_path = tmp_path / "dataset.parquet"
    pd.DataFrame(
        {
            "pickup_location_id": [1],
            "pickup_hour": [pd.Timestamp("2023-01-01 00:00:00")],
            "pickup_count": [3],
            "next_hour_pickup_count": [5],
        }
    ).to_parquet(dataset_path, index=False)

    # Act
    entity_df = load_entity_df(dataset_path)

    # Assert — feast's entity frame: entity key, timestamp, label only.
    assert list(entity_df.columns) == [
        "pickup_location_id",
        "event_timestamp",
        "next_hour_pickup_count",
    ]
    assert entity_df.loc[0, "event_timestamp"] == pd.Timestamp(
        "2023-01-01 00:00:00"
    )


def test_load_entity_df_normalizes_existing_event_timestamp(
    tmp_path: Path,
) -> None:
    # Arrange — a dataset whose event_timestamp arrives as strings.
    frame = pd.DataFrame(
        {
            "pickup_location_id": [1],
            "event_timestamp": ["2023-01-05 03:00:00"],
            "next_hour_pickup_count": [7],
            "unused_column": ["x"],
        }
    )
    dataset_path = tmp_path / "dataset.parquet"
    frame.to_parquet(dataset_path, index=False)

    # Act
    entity_df = load_entity_df(dataset_path)

    # Assert
    assert pd.api.types.is_datetime64_any_dtype(entity_df["event_timestamp"])
    assert entity_df.loc[0, "event_timestamp"] == pd.Timestamp(
        "2023-01-05 03:00:00"
    )
    assert "unused_column" not in entity_df.columns


def _load_repo_modules(repo_path: Path) -> dict[str, ModuleType]:
    """Load the repo's definition modules in dependency order.

    Sibling imports inside the repo (`from entities import …` in
    `feature_views.py`) resolve through `sys.modules`, so each freshly
    loaded module is bound under its real name only for the duration of the
    load; the caller's prior bindings are restored afterwards.
    """
    loaded: dict[str, ModuleType] = {}
    previous: dict[str, ModuleType | None] = {}
    try:
        for name in _REPO_DEFINITION_MODULES:
            loaded[name] = _exec_repo_module(repo_path, name, previous)
    finally:
        _restore_sys_modules(previous)
    return loaded


def _exec_repo_module(
    repo_path: Path, name: str, previous: dict[str, ModuleType | None]
) -> ModuleType:
    spec = spec_from_file_location(name, repo_path / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError(
            f"Cannot load feature repo module {name!r}: expected a Python "
            f"file at {repo_path / f'{name}.py'}"
        )
    module = module_from_spec(spec)
    previous[name] = sys.modules.get(name)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _restore_sys_modules(previous: dict[str, ModuleType | None]) -> None:
    for name, prior in previous.items():
        if prior is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prior
