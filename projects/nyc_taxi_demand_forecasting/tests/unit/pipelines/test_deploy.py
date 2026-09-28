from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeMlflowClient,
    FakeMlflowModule,
    FakeModelVersion,
    FakeProjectConfigLoader,
    project_config,
)
from nyc_taxi_demand_forecasting.pipelines import deploy


def _patch_seams(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    versions: list[FakeModelVersion],
) -> FakeMlflowModule:
    config = project_config(tmp_path)
    monkeypatch.setattr(
        deploy,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(deploy, "mlflow", fake_mlflow)
    monkeypatch.setattr(
        deploy, "MlflowClient", partial(FakeMlflowClient, versions=versions)
    )
    return fake_mlflow


def test_deploy_promotes_latest_version_to_champion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    fake_mlflow = _patch_seams(monkeypatch, tmp_path, [FakeModelVersion("3")])

    # Act
    deploy.run(tmp_path / "configs" / "project.yaml")

    # Assert
    client = FakeMlflowClient.instances[0]
    assert fake_mlflow.tracking_uri is not None
    assert client.alias_calls == [
        {"name": "model", "alias": "champion", "version": "3"}
    ]


def test_deploy_rejects_missing_registered_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    _patch_seams(monkeypatch, tmp_path, [])

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
        deploy.run(tmp_path / "configs" / "project.yaml")
