import math
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fakes import (
    FakeMlflowClient,
    FakeMlflowModule,
    FakeModelVersion,
    FakeProjectConfigLoader,
    FakePyfuncModel,
    project_config,
    training_frame,
)
from nyc_taxi_demand_forecasting.pipelines import monitor


@pytest.mark.parametrize(
    ("production_mean", "expected_status"),
    [
        pytest.param(112.0, "Drift Detected", id="warning_over_10pct"),
        pytest.param(110.0, "Mild Drift", id="caution_at_10pct_boundary"),
        pytest.param(106.0, "Mild Drift", id="caution_over_5pct"),
        pytest.param(105.0, "Normal", id="normal_at_5pct_boundary"),
        pytest.param(102.0, "Normal", id="normal_under_5pct"),
        pytest.param(95.0, "Normal", id="normal_at_negative_5pct_boundary"),
        pytest.param(
            90.0, "Mild Drift", id="caution_at_negative_10pct_boundary"
        ),
        pytest.param(88.0, "Drift Detected", id="warning_negative_12pct"),
    ],
)
def test_drift_stats_labels_drift_levels(
    production_mean: float, expected_status: str
) -> None:
    # Arrange
    training = pd.Series([100.0, 100.0])
    production = pd.Series([production_mean])

    # Act
    train_mean, prod_mean, drift_pct, status = monitor._drift_stats(
        training, production
    )

    # Assert
    assert train_mean == 100.0
    assert prod_mean == production_mean
    assert expected_status in status
    assert drift_pct == pytest.approx((production_mean - 100.0) / 100.0 * 100)


def test_drift_stats_zero_baseline_flags_unbounded_drift() -> None:
    # Arrange — a 0→nonzero shift is unbounded relative drift, not 0%.
    training = pd.Series([0.0, 0.0])
    production = pd.Series([5.0])

    # Act
    _, _, drift_pct, status = monitor._drift_stats(training, production)

    # Assert
    assert drift_pct == math.inf
    assert "Drift Detected" in status


def test_drift_stats_zero_baseline_stays_normal_when_unchanged() -> None:
    # Arrange
    training = pd.Series([0.0, 0.0])
    production = pd.Series([0.0])

    # Act
    _, _, drift_pct, status = monitor._drift_stats(training, production)

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
    model, version, alias = monitor._load_champion_model(client, "model")

    # Assert
    assert version == "2"
    assert alias == "@champion"
    assert model is fake_mlflow.pyfunc.model
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model@champion"]


def test_load_champion_model_falls_back_to_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — no alias registered, so the client's alias lookup raises.
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(versions={"model": [FakeModelVersion("9")]})

    # Act
    model, version, alias = monitor._load_champion_model(client, "model")

    # Assert
    assert version == "9"
    assert alias is None
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model/9"]


def test_load_champion_model_propagates_champion_load_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — the alias is set but the champion artifact itself is corrupt:
    # the monitor must fail loudly rather than silently evaluate another model.
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.load_errors = {
        "models:/model@champion": RuntimeError("corrupt artifact")
    }
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(
        versions={"model": [FakeModelVersion("9")]},
        alias_versions={("model", "champion"): FakeModelVersion("2")},
    )

    # Act / Assert
    with pytest.raises(RuntimeError, match="corrupt artifact"):
        monitor._load_champion_model(client, "model")


def test_load_champion_model_rejects_empty_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(monitor, "mlflow", fake_mlflow)
    client = FakeMlflowClient(versions={})

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
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
    assert "Alias: `@champion`" in report
    assert "| **pickup_count** |" in report
    assert "+11.72%" in report
    assert "Drift Detected" in report
    assert "| **hour** |" in report
    assert "| **month** |" in report
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model@champion"]


def test_monitor_run_reports_served_alias_on_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — no champion alias: the report must name the version actually
    # served rather than claiming @champion.
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
            versions={"model": [FakeModelVersion("9")]},
        ),
    )

    # Act
    monitor.run(tmp_path / "configs" / "project.yaml")

    # Assert
    report = (config.paths.reports / "monitoring.md").read_text(
        encoding="utf-8"
    )
    assert "Version: `9`" in report
    assert "Alias: `@champion`" not in report
    assert "latest" in report


def test_monitor_run_flattens_matrix_predictions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — pyfunc wrappers may emit a 2-D matrix; the monitor must
    # normalize it before assigning the prediction column.
    config = project_config(tmp_path)
    config.features.training_dataset_path.parent.mkdir(parents=True)
    training_frame().to_parquet(
        config.features.training_dataset_path, index=False
    )
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.model = FakePyfuncModel([1.0] * 10, as_2d=True)
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


def test_monitor_run_does_not_touch_global_rng(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — the monitor must not reseed the process-global RNG.
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
    np.random.seed(7)
    expected = np.random.rand(3)
    np.random.seed(7)

    # Act
    monitor.run(tmp_path / "configs" / "project.yaml")

    # Assert
    np.testing.assert_array_equal(np.random.rand(3), expected)
