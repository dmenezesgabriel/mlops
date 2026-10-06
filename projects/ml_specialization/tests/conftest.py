"""Shared fixture plumbing; the named fakes live in `tests/fakes.py`."""

from collections.abc import Iterator

import pytest
from fakes import reset_fake_state


@pytest.fixture(autouse=True)
def _reset_fake_state() -> Iterator[None]:
    reset_fake_state()
    yield


@pytest.fixture
def project_config_yaml() -> str:
    """A valid `configs/project.yaml` payload for tmp_path writes."""
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
