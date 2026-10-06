from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeFeastModule,
    FakeFeatureStore,
    FakeMlflowClient,
    FakeMlflowModule,
    FakeModelVersion,
    FakeProjectConfigLoader,
    FakePyfuncModel,
    entity_frame,
    import_module_for,
    project_config,
    training_frame,
)
from nyc_taxi_demand_forecasting.configuration import EvaluationConfig
from nyc_taxi_demand_forecasting.pipelines import evaluate


def _seed_entity_dataset(tmp_path: Path) -> None:
    dataset_path = project_config(tmp_path).features.training_dataset_path
    dataset_path.parent.mkdir(parents=True)
    entity_frame().to_parquet(dataset_path, index=False)


def _patch_seams(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    versions: list[FakeModelVersion],
    evaluation: EvaluationConfig | None = None,
    predictions: list[float] | None = None,
) -> None:
    config = project_config(tmp_path)
    if evaluation is not None:
        config = replace(config, evaluation=evaluation)
    FakeFeatureStore.historical_result = training_frame()
    fake_mlflow = FakeMlflowModule()
    # evaluate splits off the last 2 rows; match their targets exactly so
    # metrics land inside the configured gates.
    model_predictions = (
        predictions if predictions is not None else [19.0, 20.0]
    )
    fake_mlflow.pyfunc.model = FakePyfuncModel(model_predictions)
    monkeypatch.setattr(
        evaluate,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(evaluate, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        evaluate, "MlflowClient", partial(FakeMlflowClient, versions=versions)
    )
    monkeypatch.setattr(
        evaluate,
        "import_module",
        import_module_for({"feast": FakeFeastModule}),
    )


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
    assert client.alias_calls == [
        {"name": "model", "alias": "candidate", "version": "7"}
    ]


def test_evaluate_gate_failure_tags_failed_and_skips_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — predictions miss every target by 10.0, so the gate must
    # raise before any success tag or candidate alias reaches the registry.
    _seed_entity_dataset(tmp_path)
    _patch_seams(
        monkeypatch,
        tmp_path,
        [FakeModelVersion("7")],
        evaluation=EvaluationConfig(max_mae=0.001, max_rmse=0.001),
        predictions=[29.0, 30.0],
    )

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid MAE"):
        evaluate.run(tmp_path / "configs" / "project.yaml")

    client = FakeMlflowClient.instances[0]
    tags = {(call["key"], call["value"]) for call in client.tag_calls}
    assert tags == {
        ("evaluated", "failed"),
        ("mae", "10.0"),
        ("rmse", "10.0"),
    }
    assert client.alias_calls == []


def test_evaluate_rejects_missing_registered_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _seed_entity_dataset(tmp_path)
    _patch_seams(monkeypatch, tmp_path, [])

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
        evaluate.run(tmp_path / "configs" / "project.yaml")
