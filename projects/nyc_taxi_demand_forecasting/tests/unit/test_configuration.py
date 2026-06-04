from pathlib import Path

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
