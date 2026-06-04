from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.registry import MlflowDemandModelRegistry


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    MlflowDemandModelRegistry(config.mlflow).registered_model_name()
