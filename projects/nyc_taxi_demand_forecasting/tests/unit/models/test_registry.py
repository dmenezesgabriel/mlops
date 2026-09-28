from pathlib import Path

import pytest
from fakes import FakeMlflowModule, import_module_for, project_config
from nyc_taxi_demand_forecasting.models import registry as registry_module
from nyc_taxi_demand_forecasting.models.registry import (
    MlflowDemandModelRegistry,
)


def test_registered_model_name_sets_tracking_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(
        registry_module,
        "import_module",
        import_module_for({"mlflow": fake_mlflow}),
    )
    config = project_config(tmp_path)

    # Act
    name = MlflowDemandModelRegistry(config.mlflow).registered_model_name()

    # Assert
    assert name == "model"
    assert fake_mlflow.tracking_uri == config.mlflow.tracking_uri
