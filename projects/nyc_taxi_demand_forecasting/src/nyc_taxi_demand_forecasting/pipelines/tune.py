import logging
from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.tuning import DemandModelTuner


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    best_result = DemandModelTuner().select_best(
        config.features.training_dataset_path,
        config.training.target_column,
        config.training.test_size,
        config.feast,
        config.mlflow,
    )
    logging.getLogger(__name__).info(
        "hyperparameter_tuning_completed",
        extra={
            "best_alpha": best_result.alpha,
            "validation_mae": best_result.validation_mae,
        },
    )
