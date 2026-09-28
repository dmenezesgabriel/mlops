from functools import partial
from pathlib import Path

import feast
import pytest
from fakes import (
    FakeFeatureStore,
    FakeMlflowClient,
    FakeMlflowModule,
    FakeModelVersion,
    FakeProjectConfigLoader,
    FakePyfuncModel,
    entity_frame,
    project_config,
    training_frame,
)
from nyc_taxi_demand_forecasting.pipelines import evaluate


def _seed_entity_dataset(tmp_path: Path) -> None:
    dataset_path = project_config(tmp_path).features.training_dataset_path
    dataset_path.parent.mkdir(parents=True)
    entity_frame().to_parquet(dataset_path, index=False)


def _patch_seams(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    versions: list[FakeModelVersion],
) -> None:
    config = project_config(tmp_path)
    FakeFeatureStore.historical_result = training_frame()
    fake_mlflow = FakeMlflowModule()
    # evaluate splits off the last 2 rows; match their targets exactly so
    # metrics land inside the configured gates.
    fake_mlflow.pyfunc.model = FakePyfuncModel([19.0, 20.0])
    monkeypatch.setattr(
        evaluate,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(evaluate, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        evaluate, "MlflowClient", partial(FakeMlflowClient, versions=versions)
    )
    monkeypatch.setattr(feast, "FeatureStore", FakeFeatureStore)


def test_evaluate_scores_and_tags_latest_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _seed_entity_dataset(tmp_path)
    _patch_seams(monkeypatch, tmp_path, [FakeModelVersion("7")])

    # Act
    evaluate.run(tmp_path / "configs" / "project.yaml")

    # Assert
    client = FakeMlflowClient.instances[0]
    store = FakeFeatureStore.instances[0]
    assert store.repo_path == str(project_config(tmp_path).feast.repo_path)
    assert store.historical_calls[0][1] == [
        "hourly_pickup_demand:pickup_count",
        "hourly_pickup_demand:hour",
        "hourly_pickup_demand:day_of_week",
        "hourly_pickup_demand:is_weekend",
        "hourly_pickup_demand:month",
    ]
    tags = {(call["key"], call["value"]) for call in client.tag_calls}
    assert tags == {
        ("evaluated", "true"),
        ("mae", "0.0"),
        ("rmse", "0.0"),
    }


def test_evaluate_rejects_missing_registered_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _seed_entity_dataset(tmp_path)
    _patch_seams(monkeypatch, tmp_path, [])

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
        evaluate.run(tmp_path / "configs" / "project.yaml")
