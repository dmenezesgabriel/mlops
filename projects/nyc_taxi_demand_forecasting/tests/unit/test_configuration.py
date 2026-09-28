from pathlib import Path
from typing import cast

import pytest
import yaml
from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader


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


@pytest.mark.parametrize(
    ("section", "key", "value", "expected"),
    [
        pytest.param(
            None, "paths", "nope", "expected mapping", id="not_mapping"
        ),
        pytest.param(
            "collection",
            "taxi_type",
            123,
            "expected string",
            id="not_string",
        ),
        pytest.param(
            "collection",
            "year",
            "2023",
            "expected integer",
            id="not_integer",
        ),
        pytest.param(
            "evaluation",
            "max_mae",
            "high",
            "expected number",
            id="not_number",
        ),
        pytest.param(
            "collection",
            "months",
            [1, "two"],
            "expected integer list",
            id="not_integer_list",
        ),
    ],
)
def test_project_config_loader_rejects_invalid_sections(
    tmp_path: Path,
    section: str | None,
    key: str,
    value: object,
    expected: str,
) -> None:
    # Arrange
    raw_config = cast(dict[str, object], yaml.safe_load(_project_config()))
    _mutate(raw_config, section, key, value)
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(yaml.safe_dump(raw_config), encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match=expected):
        ProjectConfigLoader().load(config_path)


def _mutate(
    config: dict[str, object],
    section: str | None,
    key: str,
    value: object,
) -> None:
    if section is None:
        config[key] = value
        return
    section_map = cast(dict[str, object], config[section])
    section_map[key] = value


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
