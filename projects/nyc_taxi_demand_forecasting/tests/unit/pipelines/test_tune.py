from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeDemandModelTuner,
    FakeProjectConfigLoader,
    project_config,
)
from nyc_taxi_demand_forecasting.models.tuning import TuningResult
from nyc_taxi_demand_forecasting.pipelines import tune


def test_tune_runs_model_tuner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    FakeDemandModelTuner.result = TuningResult(alpha=0.5, validation_mae=1.2)
    monkeypatch.setattr(
        tune,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(tune, "DemandModelTuner", FakeDemandModelTuner)

    # Act
    tune.run(tmp_path / "configs" / "project.yaml")

    # Assert
    tuner = FakeDemandModelTuner.instances[0]
    assert tuner.select_calls == [
        (
            config.features.training_dataset_path,
            config.training.target_column,
            config.training.test_size,
            config.feast,
            config.mlflow,
        )
    ]
