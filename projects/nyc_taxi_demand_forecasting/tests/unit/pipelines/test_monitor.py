from functools import partial
from pathlib import Path

import pandas as pd
import pytest
from fakes import (
    FakeMlflowClient,
    FakeMlflowModule,
    FakeModelVersion,
    FakeProjectConfigLoader,
    project_config,
    training_frame,
)
from nyc_taxi_demand_forecasting.pipelines import monitor


@pytest.mark.parametrize(
    ("production_mean", "expected_status"),
    [
        pytest.param(112.0, "Drift Detected", id="warning_over_10pct"),
        pytest.param(106.0, "Mild Drift", id="caution_over_5pct"),
        pytest.param(102.0, "Normal", id="normal_under_5pct"),
        pytest.param(88.0, "Drift Detected", id="warning_negative_12pct"),
    ],
)
def test_pickup_drift_stats_labels_drift_levels(
    production_mean: float, expected_status: str
) -> None:
    # Arrange
    training = pd.DataFrame({"pickup_count": [100.0, 100.0]})
    production = pd.DataFrame({"pickup_count": [production_mean]})

    # Act
    train_mean, prod_mean, drift_pct, status = monitor._pickup_drift_stats(
        training, production
    )

    # Assert
    assert train_mean == 100.0
    assert prod_mean == production_mean
    assert expected_status in status
    assert drift_pct == pytest.approx((production_mean - 100.0) / 100.0 * 100)


def test_pickup_drift_stats_handles_zero_baseline() -> None:
    # Arrange
    training = pd.DataFrame({"pickup_count": [0.0, 0.0]})
    production = pd.DataFrame({"pickup_count": [5.0]})

    # Act
    _, _, drift_pct, status = monitor._pickup_drift_stats(training, production)

    # Assert
    assert drift_pct == 0.0
    assert status == "Normal"


def test_load_champion_model_returns_alias_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(
        alias_versions={("model", "champion"): FakeModelVersion("2")}
    )

    # Act
    model, version = monitor._load_champion_model(client, "model")

    # Assert
    assert version == "2"
    assert model is fake_mlflow.pyfunc.model
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model@champion"]


def test_load_champion_model_falls_back_to_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — no alias registered, so the client's alias lookup raises.
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(versions=[FakeModelVersion("9")])

    # Act
    model, version = monitor._load_champion_model(client, "model")

    # Assert
    assert version == "9"
    assert fake_mlflow.pyfunc.loaded_uris == [
        "models:/model@champion",
        "models:/model/9",
    ]


def test_load_champion_model_falls_back_when_alias_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — the pyfunc load itself fails for the alias URI.
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.load_errors = {
        "models:/model@champion": RuntimeError("alias not set")
    }
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(versions=[FakeModelVersion("9")])

    # Act
    _, version = monitor._load_champion_model(client, "model")

    # Assert
    assert version == "9"


def test_load_champion_model_rejects_empty_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.load_errors = {
        "models:/model@champion": RuntimeError("alias not set")
    }
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(versions=[])

    # Act / Assert
    with pytest.raises(ValueError, match="No model found for monitoring"):
        monitor._load_champion_model(client, "model")


def test_monitor_run_writes_monitoring_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    config.features.training_dataset_path.parent.mkdir(parents=True)
    training_frame().to_parquet(
        config.features.training_dataset_path, index=False
    )
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(
        monitor,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        monitor,
        "MlflowClient",
        partial(
            FakeMlflowClient,
            alias_versions={("model", "champion"): FakeModelVersion("2")},
        ),
    )

    # Act
    monitor.run(tmp_path / "configs" / "project.yaml")

    # Assert
    report = (config.paths.reports / "monitoring.md").read_text(
        encoding="utf-8"
    )
    assert "# Model Monitoring Report" in report
    assert "Version: `2`" in report
    assert "Drift Detected" in report
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model@champion"]
