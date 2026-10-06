from pathlib import Path

import pandas as pd
from fakes import entity_frame, training_frame
from nyc_taxi_demand_forecasting.features.feast_materialization import (
    _load_repo_modules,
)
from nyc_taxi_demand_forecasting.features.hourly_demand import (
    ENTITY_COLUMNS,
    FEATURE_COLUMNS,
    FEATURE_REFS,
    FEATURE_VIEW_NAME,
    HourlyDemandFeatureBuilder,
    load_entity_df,
)


def test_hourly_demand_feature_builder_renames_event_timestamp() -> None:
    # Arrange
    dataset = pd.DataFrame(
        {
            "pickup_location_id": [1],
            "pickup_hour": [pd.Timestamp("2023-01-01 00:00:00")],
            "pickup_count": [3],
            "hour": [0],
            "day_of_week": [6],
            "is_weekend": [True],
            "month": [1],
        }
    )

    # Act
    features = HourlyDemandFeatureBuilder().build_from_dataset(dataset)

    # Assert
    assert "event_timestamp" in features.columns
    assert features.loc[0, "pickup_count"] == 3


def test_builder_writes_feature_parquet(tmp_path: Path) -> None:
    # Arrange
    dataset_path = tmp_path / "training.parquet"
    training_frame().to_parquet(dataset_path, index=False)

    # Act
    output_path = HourlyDemandFeatureBuilder().build(
        dataset_path, tmp_path / "features" / "hourly.parquet"
    )

    # Assert
    features = pd.read_parquet(output_path)
    assert "event_timestamp" in features.columns
    assert len(features) == 10


def test_feature_refs_are_view_qualified_feature_columns() -> None:
    # Assert — every consumer must request exactly this ref set.
    assert FEATURE_REFS == (
        "hourly_pickup_demand:pickup_count",
        "hourly_pickup_demand:hour",
        "hourly_pickup_demand:day_of_week",
        "hourly_pickup_demand:is_weekend",
        "hourly_pickup_demand:month",
    )


def test_repo_feature_view_schema_matches_feature_columns() -> None:
    # The feast repo defs cannot import this package, so the schema lockstep
    # is pinned here: a feature-set change must fail loudly in one place.
    # Arrange
    repo_path = Path(__file__).resolve().parents[3] / "feature_repo"

    # Act
    modules = _load_repo_modules(repo_path)
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
    entity_frame().to_parquet(dataset_path, index=False)

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
