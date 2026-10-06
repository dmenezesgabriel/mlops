from pathlib import Path

import pytest
from ml_specialization.configuration import ProjectConfigLoader


def test_project_config_loader_resolves_project_paths(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(_project_config(), encoding="utf-8")

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.paths.raw_data == tmp_path / "data" / "raw"
    assert config.collection.source_url(1).endswith("2023-01.parquet")


def test_project_config_loader_anchors_relative_mlflow_uri_to_project_root(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(_project_config(), encoding="utf-8")

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.mlflow.tracking_uri == f"sqlite:////{tmp_path / 'mlflow.db'}"


@pytest.mark.parametrize(
    ("config_edit", "match"),
    [
        pytest.param(
            ("months: [1]", "months: [1]\n  1: a\n  '1': b"),
            "expected string key",
            id="non_string_collection_keys",
        ),
        pytest.param(
            ("months: [1]", "months: [1]\n  on: x"),
            "expected string key",
            id="yaml_bool_collection_key",
        ),
        pytest.param(
            ("months: [1]", "months: [on, off]"),
            "expected integer list",
            id="bool_months",
        ),
        pytest.param(
            ("year: 2023", "year: yes"),
            "expected integer",
            id="bool_year",
        ),
        pytest.param(
            ("test_size: 0.2", "test_size: on"),
            "expected number",
            id="bool_test_size",
        ),
    ],
)
def test_project_config_loader_rejects_yaml_coerced_values(
    tmp_path: Path, config_edit: tuple[str, str], match: str
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    old, new = config_edit
    config_path.write_text(
        _project_config().replace(old, new), encoding="utf-8"
    )

    # Act / Assert
    with pytest.raises(ValueError, match=match):
        ProjectConfigLoader().load(config_path)


def test_project_config_loader_rejects_config_outside_configs_dir(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = tmp_path / "project.yaml"
    config_path.write_text(_project_config(), encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="configs/"):
        ProjectConfigLoader().load(config_path)


def test_project_config_loader_passes_through_in_memory_sqlite_uri(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        _project_config().replace(
            "sqlite:///mlflow.db", '"sqlite:///:memory:"'
        ),
        encoding="utf-8",
    )

    # Act
    config = ProjectConfigLoader().load(config_path)

    # Assert
    assert config.mlflow.tracking_uri == "sqlite:///:memory:"


def _project_config() -> str:
    return """
paths:
  raw_data: data/raw
  interim_data: data/interim
  processed_data: data/processed
  models: models
  reports: reports
collection:
  year: 2023
  months: [1]
  taxi_type: yellow
  source_url_template: https://example.test/{year}-{month:02d}.parquet
features:
  training_dataset_path: data/processed/training_dataset.parquet
  offline_features_path: data/processed/hourly_demand_features.parquet
feast:
  repo_path: feature_repo
mlflow:
  tracking_uri: sqlite:///mlflow.db
  experiment_name: test
  registered_model_name: model
training:
  target_column: next_hour_pickup_count
  test_size: 0.2
  random_state: 42
evaluation:
  max_mae: 1.0
  max_rmse: 2.0
"""
