import logging
from pathlib import Path

import mlflow
from mlflow.client import MlflowClient
from mlflow.exceptions import MlflowException

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # Connect to MLflow Model Registry
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    client = MlflowClient()

    model_name = config.mlflow.registered_model_name

    # Promote only the gated candidate: the evaluate pipeline binds this
    # alias after the quality gate passes, so an unevaluated version can
    # never reach champion.
    try:
        candidate_version = client.get_model_version_by_alias(
            model_name, "candidate"
        )
    except MlflowException as err:
        raise ValueError(
            f"No evaluated candidate for model {model_name}: expected the "
            "evaluate pipeline to set the 'candidate' alias"
        ) from err

    # Promote model by setting the alias "champion"
    client.set_registered_model_alias(
        name=model_name,
        alias="champion",
        version=candidate_version.version,
    )

    logging.getLogger(__name__).info(
        "model_deployment_completed",
        extra={
            "model_name": model_name,
            "version": candidate_version.version,
            "alias": "champion",
        },
    )
