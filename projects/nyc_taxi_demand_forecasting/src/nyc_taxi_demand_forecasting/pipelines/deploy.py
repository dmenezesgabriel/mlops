import logging
from pathlib import Path

import mlflow
from mlflow.client import MlflowClient

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # Connect to MLflow Model Registry
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    client = MlflowClient()

    model_name = config.mlflow.registered_model_name

    # Fetch latest version
    latest_versions = client.get_latest_versions(name=model_name)
    if not latest_versions:
        raise ValueError(f"No registered model found with name {model_name}")

    latest_version = latest_versions[0]

    # Promote model by setting the alias "champion"
    client.set_registered_model_alias(
        name=model_name,
        alias="champion",
        version=latest_version.version,
    )

    logging.getLogger(__name__).info(
        "model_deployment_completed",
        extra={
            "model_name": model_name,
            "version": latest_version.version,
            "alias": "champion",
        },
    )
