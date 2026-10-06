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
    versions: dict[str, list[FakeModelVersion]],
    alias_versions: dict[tuple[str, str], FakeModelVersion] | None = None,
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
        deploy,
        "MlflowClient",
        partial(
            FakeMlflowClient,
            versions=versions,
            alias_versions=alias_versions,
        ),
    )
    return fake_mlflow


def test_deploy_promotes_candidate_to_champion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — the evaluate pipeline gated v3 and marked it deployable.
    fake_mlflow = _patch_seams(
        monkeypatch,
        tmp_path,
        {"model": [FakeModelVersion("3")]},
        alias_versions={("model", "candidate"): FakeModelVersion("3")},
    )

    # Act
    deploy.run(tmp_path / "configs" / "project.yaml")

    # Assert
    client = FakeMlflowClient.instances[0]
    assert fake_mlflow.tracking_uri is not None
    assert client.alias_calls == [
        {"name": "model", "alias": "champion", "version": "3"}
    ]


def test_deploy_refuses_unevaluated_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — v9 is registered but the candidate alias was never set,
    # so no version was gated for promotion.
    _patch_seams(monkeypatch, tmp_path, {"model": [FakeModelVersion("9")]})

    # Act / Assert
    with pytest.raises(ValueError, match="candidate"):
        deploy.run(tmp_path / "configs" / "project.yaml")

    client = FakeMlflowClient.instances[0]
    assert client.alias_calls == []
