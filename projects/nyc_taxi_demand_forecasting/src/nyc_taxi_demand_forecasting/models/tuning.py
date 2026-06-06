from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import mlflow
import pandas as pd
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import FeastConfig, MlflowConfig
from nyc_taxi_demand_forecasting.models.training import (
    DemandDatasetSplitter,
    RidgeDemandRegressor,
)


@dataclass(frozen=True)
class TuningResult:
    alpha: float
    validation_mae: float


class DemandModelTuner:
    """Run a parameter sweep over alpha regularizations logged to MLflow.

    Example:
        DemandModelTuner().select_best(dataset_path, "target_col", 0.2, feast_config, mlflow_config)
    """

    _feature_columns = (
        "pickup_count",
        "hour",
        "day_of_week",
        "is_weekend",
        "month",
    )

    def select_best(
        self,
        dataset_path: Path,
        target_column: str,
        test_size: float,
        feast_config: FeastConfig,
        mlflow_config: MlflowConfig,
    ) -> TuningResult:
        # Load entities dataframe
        entity_df = pd.read_parquet(dataset_path)
        if "event_timestamp" not in entity_df.columns:
            entity_df["event_timestamp"] = pd.to_datetime(
                entity_df["pickup_hour"]
            )
        entity_df["event_timestamp"] = pd.to_datetime(
            entity_df["event_timestamp"]
        )
        entity_df = entity_df[
            ["pickup_location_id", "event_timestamp", "next_hour_pickup_count"]
        ]

        # Fetch historical features from Feast Feature Store
        feature_store_type = import_module("feast").FeatureStore
        store = feature_store_type(repo_path=str(feast_config.repo_path))
        training_data = store.get_historical_features(
            entity_df=entity_df,
            features=[
                "hourly_pickup_demand:pickup_count",
                "hourly_pickup_demand:hour",
                "hourly_pickup_demand:day_of_week",
                "hourly_pickup_demand:is_weekend",
                "hourly_pickup_demand:month",
            ],
        ).to_df()

        train_frame, val_frame = DemandDatasetSplitter().split(
            training_data, test_size
        )

        mlflow.set_tracking_uri(mlflow_config.tracking_uri)
        mlflow.set_experiment(mlflow_config.experiment_name)

        best_alpha = 1.0
        best_mae = float("inf")

        # Run hyperparameter sweep
        alphas = [0.1, 1.0, 10.0, 100.0]
        with mlflow.start_run(run_name="hyperparameter_tuning"):
            for alpha in alphas:
                with mlflow.start_run(
                    run_name=f"tune_ridge_alpha_{alpha}", nested=True
                ):
                    model = RidgeDemandRegressor(alpha=alpha)
                    model.fit(
                        train_frame.loc[:, list(self._feature_columns)],
                        train_frame[target_column],
                    )
                    predictions = model.predict(
                        val_frame.loc[:, list(self._feature_columns)]
                    )
                    metrics = RegressionMetricCalculator().calculate(
                        val_frame[target_column], predictions
                    )

                    mlflow.log_param("alpha", alpha)
                    mlflow.log_metrics(
                        {
                            "mae": metrics.mae,
                            "rmse": metrics.rmse,
                            "r2": metrics.r2,
                        }
                    )

                    if metrics.mae < best_mae:
                        best_mae = metrics.mae
                        best_alpha = alpha

            # Log the best parameter determined by tuning on the parent run
            mlflow.log_param("best_alpha", best_alpha)
            mlflow.log_metric("best_validation_mae", best_mae)

        return TuningResult(alpha=best_alpha, validation_mae=best_mae)
