from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import cast

import mlflow
import optuna
import pandas as pd
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import (
    FeastConfig,
    MlflowConfig,
)
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
        DemandModelTuner().select_best(
            dataset_path, "target_col", 0.2, feast_config, mlflow_config
        )
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
        entity_df = self._load_entity_df(dataset_path)
        training_data = self._fetch_features(entity_df, feast_config)
        train_frame, val_frame = DemandDatasetSplitter().split(
            training_data, test_size
        )
        self._init_mlflow(mlflow_config)

        best_alpha, best_mae = self._run_optuna_study(
            train_frame, val_frame, target_column
        )
        return TuningResult(alpha=best_alpha, validation_mae=best_mae)

    def _load_entity_df(self, dataset_path: Path) -> pd.DataFrame:
        entity_df = pd.read_parquet(dataset_path)
        if "event_timestamp" not in entity_df.columns:
            entity_df["event_timestamp"] = pd.to_datetime(
                entity_df["pickup_hour"]
            )
        entity_df["event_timestamp"] = pd.to_datetime(
            entity_df["event_timestamp"]
        )
        return entity_df[
            [
                "pickup_location_id",
                "event_timestamp",
                "next_hour_pickup_count",
            ]
        ]

    def _fetch_features(
        self, entity_df: pd.DataFrame, feast_config: FeastConfig
    ) -> pd.DataFrame:
        feature_store_type = import_module("feast").FeatureStore
        store = feature_store_type(repo_path=str(feast_config.repo_path))
        return cast(
            pd.DataFrame,
            store.get_historical_features(
                entity_df=entity_df,
                features=[
                    "hourly_pickup_demand:pickup_count",
                    "hourly_pickup_demand:hour",
                    "hourly_pickup_demand:day_of_week",
                    "hourly_pickup_demand:is_weekend",
                    "hourly_pickup_demand:month",
                ],
            ).to_df(),
        )

    def _init_mlflow(self, mlflow_config: MlflowConfig) -> None:
        mlflow.set_tracking_uri(mlflow_config.tracking_uri)
        mlflow.set_experiment(mlflow_config.experiment_name)

    def _run_optuna_study(
        self,
        train_frame: pd.DataFrame,
        val_frame: pd.DataFrame,
        target_column: str,
    ) -> tuple[float, float]:
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction="minimize")

        def objective(trial: optuna.Trial) -> float:
            alpha = trial.suggest_float("alpha", 1e-3, 1e4, log=True)
            return self._evaluate_trial(
                trial.number,
                alpha,
                train_frame,
                val_frame,
                target_column,
            )

        with mlflow.start_run(run_name="hyperparameter_tuning"):
            study.optimize(objective, n_trials=25)
            best_alpha = study.best_params["alpha"]
            best_mae = study.best_value
            mlflow.log_param("best_alpha", best_alpha)
            mlflow.log_metric("best_validation_mae", best_mae)

        return best_alpha, best_mae

    def _evaluate_trial(
        self,
        trial_num: int,
        alpha: float,
        train_frame: pd.DataFrame,
        val_frame: pd.DataFrame,
        target_column: str,
    ) -> float:
        with mlflow.start_run(
            run_name=f"tune_ridge_trial_{trial_num}", nested=True
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
            return metrics.mae
