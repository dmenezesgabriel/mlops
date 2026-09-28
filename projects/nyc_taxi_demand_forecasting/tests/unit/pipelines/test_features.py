from datetime import datetime
from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeFeastMaterializer,
    FakeFeatureStore,
    FakeProjectConfigLoader,
    FakeRecordingBuilder,
    project_config,
)
from nyc_taxi_demand_forecasting.pipelines import features


def test_features_run_builds_datasets_and_materializes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    monkeypatch.setattr(
        features,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(
        features, "NextHourDemandDatasetBuilder", FakeRecordingBuilder
    )
    monkeypatch.setattr(
        features, "HourlyDemandFeatureBuilder", FakeRecordingBuilder
    )
    monkeypatch.setattr(
        features, "LocalFeastMaterializer", FakeFeastMaterializer
    )
    monkeypatch.setattr(features, "FeatureStore", FakeFeatureStore)

    # Act
    features.run(tmp_path / "configs" / "project.yaml")

    # Assert
    dataset_builder, feature_builder = FakeRecordingBuilder.instances
    assert dataset_builder.build_calls == [
        (
            config.paths.interim_data / "yellow_taxi_trips.parquet",
            config.features.training_dataset_path,
        )
    ]
    assert feature_builder.build_calls == [
        (
            config.features.training_dataset_path,
            config.features.offline_features_path,
        )
    ]
    materializer = FakeFeastMaterializer.instances[0]
    assert materializer.applied_repos == [config.feast.repo_path]
    store = FakeFeatureStore.instances[0]
    # months (1, 3) of year 2023: 2023-01-01 .. 2023-03-31 + 1 day
    assert store.materialized_windows == [
        (datetime(2023, 1, 1), datetime(2023, 4, 1))
    ]
