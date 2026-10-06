from datetime import datetime
from functools import partial
from pathlib import Path

import pandas as pd
import pytest
from fakes import (
    FakeFeastMaterializer,
    FakeFeastModule,
    FakeFeatureStore,
    FakeProjectConfigLoader,
    FakeRecordingBuilder,
    import_module_for,
    project_config,
)
from nyc_taxi_demand_forecasting.pipelines import features


def _stub_builders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        features, "NextHourDemandDatasetBuilder", FakeRecordingBuilder
    )
    monkeypatch.setattr(
        features, "HourlyDemandFeatureBuilder", FakeRecordingBuilder
    )
    monkeypatch.setattr(
        features, "LocalFeastMaterializer", FakeFeastMaterializer
    )
    monkeypatch.setattr(
        features,
        "import_module",
        import_module_for({"feast": FakeFeastModule}),
    )


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
    _stub_builders(monkeypatch)
    # The materialize window follows the built dataset's timestamps, not the
    # configured months — a stray-month file can no longer slip features past
    # the online store (or shrink the window below the data's real range).
    config.features.offline_features_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "event_timestamp": pd.to_datetime(
                ["2023-01-05 00:00:00", "2023-03-10 23:00:00"]
            )
        }
    ).to_parquet(config.features.offline_features_path, index=False)

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
    # max event_timestamp is hourly-aligned; the +1h end covers the last row
    assert store.materialized_windows == [
        (datetime(2023, 1, 5), datetime(2023, 3, 11))
    ]


def test_features_run_rejects_empty_offline_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    monkeypatch.setattr(
        features,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    _stub_builders(monkeypatch)
    config.features.offline_features_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {"event_timestamp": pd.Series(dtype="datetime64[ns]")}
    ).to_parquet(config.features.offline_features_path, index=False)

    # Act / Assert
    with pytest.raises(ValueError, match="expected at least one feature row"):
        features.run(tmp_path / "configs" / "project.yaml")
    assert FakeFeatureStore.instances[0].materialized_windows == []
