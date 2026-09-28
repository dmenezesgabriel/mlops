import logging
from pathlib import Path

import mlflow
import pandas as pd

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.training import DemandModelTrainer


def _resolve_best_alpha(tracking_uri: str, experiment_name: str) -> float:
    """Best alpha from the latest hyperparameter tuning run, else 1.0."""
    mlflow.set_tracking_uri(tracking_uri)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        return 1.0

    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.mlflow.runName = 'hyperparameter_tuning'",
        order_by=["start_time DESC"],
        max_results=1,
    )
    if (
        not isinstance(runs, pd.DataFrame)
        or runs.empty
        or "params.best_alpha" not in runs.columns
    ):
        return 1.0

    best_alpha_str = runs.iloc[0]["params.best_alpha"]
    if best_alpha_str is None or str(best_alpha_str) == "nan":
        return 1.0

    best_alpha = float(best_alpha_str)
    logging.getLogger(__name__).info(
        "retrieved_best_alpha_from_tuning",
        extra={"alpha": best_alpha},
    )
    return best_alpha


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # Resolve the best alpha from the hyperparameter tuning run in MLflow
    best_alpha = _resolve_best_alpha(
        config.mlflow.tracking_uri, config.mlflow.experiment_name
    )

    DemandModelTrainer().train(
        config.features.training_dataset_path,
        config.paths.models,
        config.training,
        config.mlflow,
        config.feast,
        alpha=best_alpha,
    )
