from functools import partial
from pathlib import Path

import pandas as pd
import pytest
from fakes import (
    FakeDemandModelTrainer,
    FakeMlflowExperiment,
    FakeMlflowModule,
    FakeProjectConfigLoader,
    project_config,
)
from nyc_taxi_demand_forecasting.pipelines import train


def test_resolve_best_alpha_defaults_without_experiment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setattr(train, "mlflow", FakeMlflowModule())

    # Act / Assert
    assert train._resolve_best_alpha("sqlite:///x.db", "exp") == 1.0


@pytest.mark.parametrize(
    ("search_result", "expected"),
    [
        pytest.param([], 1.0, id="non_frame_result"),
        pytest.param(pd.DataFrame(), 1.0, id="empty_runs"),
        pytest.param(
            pd.DataFrame({"other": [1]}), 1.0, id="missing_alpha_column"
        ),
        pytest.param(
            pd.DataFrame({"params.best_alpha": [None]}),
            1.0,
            id="null_alpha",
        ),
        pytest.param(
            pd.DataFrame({"params.best_alpha": ["nan"]}),
            1.0,
            id="nan_alpha",
        ),
        pytest.param(
            pd.DataFrame({"params.best_alpha": ["0.05"]}),
            0.05,
            id="valid_alpha",
        ),
    ],
)
def test_resolve_best_alpha_reads_latest_tuning_run(
    monkeypatch: pytest.MonkeyPatch,
    search_result: object,
    expected: float,
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.experiment = FakeMlflowExperiment("exp-1")
    fake_mlflow.search_result = search_result
    monkeypatch.setattr(train, "mlflow", fake_mlflow)

    # Act
    alpha = train._resolve_best_alpha("sqlite:///x.db", "exp")

    # Assert
    assert alpha == expected


def test_run_resolves_alpha_and_invokes_trainer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.experiment = FakeMlflowExperiment("exp-1")
    fake_mlflow.search_result = pd.DataFrame({"params.best_alpha": ["0.25"]})
    monkeypatch.setattr(
        train,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(train, "mlflow", fake_mlflow)
    monkeypatch.setattr(train, "DemandModelTrainer", FakeDemandModelTrainer)

    # Act
    train.run(tmp_path / "configs" / "project.yaml")

    # Assert
    trainer = FakeDemandModelTrainer.instances[0]
    assert trainer.train_calls == [
        {
            "dataset_path": config.features.training_dataset_path,
            "model_directory": config.paths.models,
            "training_config": config.training,
            "mlflow_config": config.mlflow,
            "feast_config": config.feast,
            "alpha": 0.25,
        }
    ]
