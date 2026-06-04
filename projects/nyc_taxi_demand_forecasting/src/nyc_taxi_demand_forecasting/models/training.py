from importlib import import_module
from pathlib import Path
from typing import Protocol

import pandas as pd

from nyc_taxi_demand_forecasting.configuration import MlflowConfig, TrainingConfig
from nyc_taxi_demand_forecasting.evaluation.metrics import (
    RegressionMetricCalculator,
    RegressionMetrics,
)


class DemandRegressor(Protocol):
    def fit(self, features: pd.DataFrame, target: pd.Series) -> object:
        pass

    def predict(self, features: pd.DataFrame) -> object:
        pass


class MedianDemandRegressor:
    def __init__(self) -> None:
        self._median_demand = 0.0

    def fit(self, features: pd.DataFrame, target: pd.Series) -> object:
        self._median_demand = float(target.median())
        return self

    def predict(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series([self._median_demand] * len(features), index=features.index)


class DemandModelTrainer:
    """Train and log a compact demand forecasting model.

    Example:
        DemandModelTrainer().train(dataset_path, models_path, training, mlflow)
    """

    _feature_columns = ("pickup_count", "hour", "day_of_week", "is_weekend", "month")

    def train(
        self,
        dataset_path: Path,
        model_directory: Path,
        training_config: TrainingConfig,
        mlflow_config: MlflowConfig,
    ) -> RegressionMetrics:
        dataset = pd.read_parquet(dataset_path)
        train_frame, test_frame = self._split(dataset, training_config.test_size)
        model = self._fit_model(train_frame, training_config)
        predictions = pd.Series(model.predict(test_frame.loc[:, list(self._feature_columns)]))
        metrics = RegressionMetricCalculator().calculate(
            test_frame[training_config.target_column], predictions
        )
        self._log_model(metrics, model_directory, mlflow_config)
        return metrics

    def _split(self, dataset: pd.DataFrame, test_size: float) -> tuple[pd.DataFrame, pd.DataFrame]:
        split_index = max(1, int(len(dataset) * (1 - test_size)))
        return dataset.iloc[:split_index].copy(), dataset.iloc[split_index:].copy()

    def _fit_model(self, train_frame: pd.DataFrame, config: TrainingConfig) -> DemandRegressor:
        model = MedianDemandRegressor()
        model.fit(
            train_frame.loc[:, list(self._feature_columns)], train_frame[config.target_column]
        )
        return model

    def _log_model(
        self, metrics: RegressionMetrics, model_directory: Path, config: MlflowConfig
    ) -> None:
        model_directory.mkdir(parents=True, exist_ok=True)
        mlflow = import_module("mlflow")
        mlflow.set_tracking_uri(config.tracking_uri)
        mlflow.set_experiment(config.experiment_name)
        with mlflow.start_run(run_name="demand_model"):
            mlflow.log_metrics({"mae": metrics.mae, "rmse": metrics.rmse, "r2": metrics.r2})
            mlflow.log_text(
                "MedianDemandRegressor predicts the training target median.",
                "model_summary.txt",
            )
