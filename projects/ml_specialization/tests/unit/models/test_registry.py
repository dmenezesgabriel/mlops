from pathlib import Path

import pytest
from fakes import (
    FakeMlflowClient,
    FakeMlflowClientModule,
    import_module_for,
)
from ml_specialization.configuration import MlflowConfig
from ml_specialization.models import registry as registry_module
from ml_specialization.models.registry import MlflowDemandModelRegistry


def test_promote_champion_uses_configured_tracking_uri(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — the configured URI must reach the client; the ambient
    # default is forbidden (it writes a stray mlflow.db to the cwd).
    monkeypatch.setattr(
        registry_module,
        "import_module",
        import_module_for({"mlflow.client": FakeMlflowClientModule()}),
    )
    config = MlflowConfig(
        tracking_uri=f"sqlite:///{tmp_path}/registry.db",
        experiment_name="experiment",
        registered_model_name="model",
    )

    # Act
    MlflowDemandModelRegistry(config).promote_champion("model", "3")

    # Assert
    client = FakeMlflowClient.instances[0]
    assert client.tracking_uri == config.tracking_uri
    assert client.alias_calls == [
        {"name": "model", "alias": "champion", "version": "3"}
    ]
