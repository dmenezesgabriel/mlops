from pathlib import Path

import pytest
from fakes import (
    FakeFeastModule,
    FakeFeatureStore,
    FakeMlflowModule,
    entity_frame,
    import_module_for,
    project_config,
    training_frame,
)
from nyc_taxi_demand_forecasting.configuration import ProjectConfig
from nyc_taxi_demand_forecasting.models import tuning as tuning_module
from nyc_taxi_demand_forecasting.models.tuning import (
    DemandModelTuner,
    TuningResult,
)


def test_select_best_runs_optuna_study_and_logs_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config, dataset_path, fake_mlflow = _arrange_tuning_seams(
        tmp_path, monkeypatch
    )

    # Act
    result = DemandModelTuner().select_best(
        dataset_path,
        config.training.target_column,
        config.training.test_size,
        config.feast,
        config.mlflow,
    )

    # Assert
    assert isinstance(result, TuningResult)
    assert 1e-3 <= result.alpha <= 1e4
    assert result.validation_mae >= 0
    _assert_study_logged(fake_mlflow, result, config)
    _assert_historical_lookup()


def _arrange_tuning_seams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ProjectConfig, Path, FakeMlflowModule]:
    config = project_config(tmp_path)
    dataset_path = tmp_path / "entities.parquet"
    entity_frame().to_parquet(dataset_path, index=False)
    FakeFeatureStore.historical_result = training_frame()
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(
        tuning_module,
        "import_module",
        import_module_for({"feast": FakeFeastModule}),
    )
    monkeypatch.setattr(tuning_module, "mlflow", fake_mlflow)
    return config, dataset_path, fake_mlflow


def _assert_study_logged(
    fake_mlflow: FakeMlflowModule,
    result: TuningResult,
    config: ProjectConfig,
) -> None:
    assert fake_mlflow.tracking_uri == config.mlflow.tracking_uri
    assert fake_mlflow.experiment_name == "test_experiment"
    assert "hyperparameter_tuning" in fake_mlflow.run_names
    assert "tune_ridge_trial_0" in fake_mlflow.run_names
    assert fake_mlflow.params["best_alpha"] == result.alpha
    assert fake_mlflow.metrics["best_validation_mae"] == (
        result.validation_mae
    )


def _assert_historical_lookup() -> None:
    store = FakeFeatureStore.instances[0]
    entity_arg, features_arg = store.historical_calls[0]
    assert "event_timestamp" in entity_arg.columns
    assert "hourly_pickup_demand:pickup_count" in features_arg
