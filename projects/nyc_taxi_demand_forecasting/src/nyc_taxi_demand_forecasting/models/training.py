from importlib import import_module
from pathlib import Path
from typing import Protocol

import mlflow
import mlflow.pyfunc
import numpy as np
import numpy.typing as npt
import pandas as pd
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import (
    FeastConfig,
    MlflowConfig,
    TrainingConfig,
)
from nyc_taxi_demand_forecasting.evaluation.metrics import RegressionMetrics


class DemandRegressor(Protocol):
    def fit(
        self, features: pd.DataFrame, target: pd.Series
    ) -> "DemandRegressor":
        pass

    def predict(self, features: pd.DataFrame) -> pd.Series:
        pass


class MedianDemandRegressor:
    def __init__(self) -> None:
        self._median_demand = 0.0

    def fit(
        self, features: pd.DataFrame, target: pd.Series
    ) -> "MedianDemandRegressor":
        self._median_demand = float(target.median())
        return self

    def predict(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series(
            [self._median_demand] * len(features), index=features.index
        )


class LinearDemandRegressor:
    def __init__(self) -> None:
        self._coefficients: npt.NDArray[np.float64] | None = None

    def fit(
        self, features: pd.DataFrame, target: pd.Series
    ) -> "LinearDemandRegressor":
        feature_matrix = self._with_intercept(features)
        target_values = target.astype(float).to_numpy()
        coefficients: npt.NDArray[np.float64] = np.asarray(
            np.linalg.lstsq(feature_matrix, target_values, rcond=None)[0],
            dtype=np.float64,
        )
        self._coefficients = coefficients
        return self

    def predict(self, features: pd.DataFrame) -> pd.Series:
        if self._coefficients is None:
            raise ValueError(
                "Invalid linear demand regressor state: expected fitted coefficients"
            )

        predictions = self._with_intercept(features) @ self._coefficients
        return pd.Series(predictions, index=features.index)

    def _with_intercept(
        self, features: pd.DataFrame
    ) -> npt.NDArray[np.float64]:
        feature_values = features.astype(float).to_numpy(dtype=np.float64)
        return np.column_stack(
            [np.ones(len(features), dtype=np.float64), feature_values]
        )


class RidgeDemandRegressor:
    """Ridge regression solved via the closed-form equation."""

    def __init__(self, alpha: float = 1.0) -> None:
        self.alpha = alpha
        self._coefficients: npt.NDArray[np.float64] | None = None

    def fit(
        self, features: pd.DataFrame, target: pd.Series
    ) -> "RidgeDemandRegressor":
        feature_matrix = self._with_intercept(features)
        target_values = target.astype(float).to_numpy()
        xtx = feature_matrix.T @ feature_matrix
        identity = np.eye(xtx.shape[0])
        identity[0, 0] = 0.0  # do not penalize intercept
        xtx_regularized = xtx + self.alpha * identity
        self._coefficients = np.asarray(
            np.linalg.solve(xtx_regularized, feature_matrix.T @ target_values),
            dtype=np.float64,
        )
        return self

    def predict(self, features: pd.DataFrame) -> pd.Series:
        if self._coefficients is None:
            raise ValueError(
                "Invalid Ridge regressor state: expected fitted coefficients"
            )

        predictions = self._with_intercept(features) @ self._coefficients
        return pd.Series(predictions, index=features.index)

    def _with_intercept(
        self, features: pd.DataFrame
    ) -> npt.NDArray[np.float64]:
        feature_values = features.astype(float).to_numpy(dtype=np.float64)
        return np.column_stack(
            [np.ones(len(features), dtype=np.float64), feature_values]
        )


class PyfuncDemandModel(mlflow.pyfunc.PythonModel):  # type: ignore[name-defined]
    """MLflow PyFunc wrapper for nyc-taxi demand forecasting models."""

    def __init__(self, model: DemandRegressor) -> None:
        self.model = model

    def predict(self, context: object, model_input: pd.DataFrame) -> pd.Series:
        return self.model.predict(model_input)


class DemandDatasetSplitter:
    """Split ordered forecasting rows into train and holdout frames.

    Example:
        DemandDatasetSplitter().split(dataset, test_size=0.2)
    """

    def split(
        self, dataset: pd.DataFrame, test_size: float
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        split_index = max(1, int(len(dataset) * (1 - test_size)))
        return dataset.iloc[:split_index].copy(), dataset.iloc[
            split_index:
        ].copy()


class DemandModelTrainer:
    """Train and log a compact demand forecasting model.

    Example:
        DemandModelTrainer().train(dataset_path, models_path, training, mlflow, feast)
    """

    _feature_columns = (
        "pickup_count",
        "hour",
        "day_of_week",
        "is_weekend",
        "month",
    )

    def __init__(self, splitter: DemandDatasetSplitter | None = None) -> None:
        self._splitter = splitter or DemandDatasetSplitter()

    def train(
        self,
        dataset_path: Path,
        model_directory: Path,
        training_config: TrainingConfig,
        mlflow_config: MlflowConfig,
        feast_config: FeastConfig,
        alpha: float = 1.0,
    ) -> RegressionMetrics:
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

        train_frame, test_frame = self._splitter.split(
            training_data, training_config.test_size
        )
        model = RidgeDemandRegressor(alpha=alpha)
        model.fit(
            train_frame.loc[:, list(self._feature_columns)],
            train_frame[training_config.target_column],
        )

        predictions = model.predict(
            test_frame.loc[:, list(self._feature_columns)]
        )
        metrics = RegressionMetricCalculator().calculate(
            test_frame[training_config.target_column], predictions
        )

        self._log_model(model, metrics, alpha, mlflow_config)
        return metrics

    def _log_model(
        self,
        model: RidgeDemandRegressor,
        metrics: RegressionMetrics,
        alpha: float,
        config: MlflowConfig,
    ) -> None:
        mlflow.set_tracking_uri(config.tracking_uri)
        mlflow.set_experiment(config.experiment_name)
        with mlflow.start_run(run_name="demand_model"):
            mlflow.log_param("alpha", alpha)
            mlflow.log_metrics(
                {"mae": metrics.mae, "rmse": metrics.rmse, "r2": metrics.r2}
            )
            mlflow.log_text(
                f"RidgeDemandRegressor predicts demand with alpha={alpha}.",
                "model_summary.txt",
            )
            # Log & register PyFunc model
            pyfunc_model = PyfuncDemandModel(model)
            mlflow.pyfunc.log_model(
                artifact_path="model",
                python_model=pyfunc_model,
                registered_model_name=config.registered_model_name,
            )
