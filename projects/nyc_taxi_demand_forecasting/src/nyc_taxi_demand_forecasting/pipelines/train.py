import logging
from pathlib import Path

import mlflow
import pandas as pd

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.training import DemandModelTrainer


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # Resolve the best alpha from the hyperparameter tuning run in MLflow
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    experiment = mlflow.get_experiment_by_name(config.mlflow.experiment_name)
    best_alpha = 1.0

    if experiment is not None:
        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="tags.mlflow.runName = 'hyperparameter_tuning'",
            order_by=["start_time DESC"],
            max_results=1,
        )
        if (
            isinstance(runs, pd.DataFrame)
            and not runs.empty
            and "params.best_alpha" in runs.columns
        ):
            best_alpha_str = runs.iloc[0]["params.best_alpha"]
            if best_alpha_str is not None and str(best_alpha_str) != "nan":
                best_alpha = float(best_alpha_str)
                logging.getLogger(__name__).info(
                    "retrieved_best_alpha_from_tuning",
                    extra={"alpha": best_alpha},
                )

    DemandModelTrainer().train(
        config.features.training_dataset_path,
        config.paths.models,
        config.training,
        config.mlflow,
        config.feast,
        alpha=best_alpha,
    )
