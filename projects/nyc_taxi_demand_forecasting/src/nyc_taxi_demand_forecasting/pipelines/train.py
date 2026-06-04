from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.training import DemandModelTrainer


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    DemandModelTrainer().train(
        config.features.training_dataset_path,
        config.paths.models,
        config.training,
        config.mlflow,
    )
