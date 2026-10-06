import math
from importlib import import_module
from pathlib import Path
from typing import Protocol

import mlflow
import mlflow.pyfunc
import numpy as np
import numpy.typing as npt
import pandas as pd
from mlflow.pyfunc.model import PythonModel
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import (
    FeastConfig,
    MlflowConfig,
    TrainingConfig,
)
from nyc_taxi_demand_forecasting.evaluation.metrics import RegressionMetrics
from nyc_taxi_demand_forecasting.features.hourly_demand import (
    FEATURE_COLUMNS,
    FEATURE_REFS,
    load_entity_df,
)


class DemandRegressor(Protocol):
    def fit(
        self, features: pd.DataFrame, target: pd.Series
    ) -> "DemandRegressor": ...

    def predict(self, features: pd.DataFrame) -> pd.Series: ...


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


class PyfuncDemandModel(PythonModel):
    """MLflow PyFunc wrapper for nyc-taxi demand forecasting models."""

    def __init__(self, model: DemandRegressor) -> None:
        self.model = model

    # mlflow documents ``predict(model_input)``-shaped overrides without
    # ``context``/``params`` as valid; the upstream stub signature is broader.
    def predict(self, context: object, model_input: pd.DataFrame) -> pd.Series:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.model.predict(model_input)


class DemandDatasetSplitter:
    """Split ordered forecasting rows into train and holdout frames.

    The last ``ceil(n * test_size)`` rows form the holdout, clamped so the
    train frame always keeps at least one row.

    Example:
        DemandDatasetSplitter().split(dataset, test_size=0.2)
    """

    def split(
        self, dataset: pd.DataFrame, test_size: float
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not 0 < test_size < 1:
            raise ValueError(
                f"Invalid test_size {test_size}: expected 0 < test_size < 1"
            )
        if len(dataset) < 2:
            raise ValueError(
                f"Invalid dataset of {len(dataset)} rows: "
                "expected at least 2 rows to split"
            )
        holdout_size = min(
            math.ceil(len(dataset) * test_size), len(dataset) - 1
        )
        split_index = len(dataset) - holdout_size
        return dataset.iloc[:split_index].copy(), dataset.iloc[
            split_index:
        ].copy()


class DemandModelTrainer:
    """Train and log a compact demand forecasting model.

    Example:
        DemandModelTrainer().train(dataset_path, models_path, training, mlflow, feast)
    """

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
        entity_df = load_entity_df(dataset_path)

        # Fetch historical features from Feast Feature Store
        feature_store_type = import_module("feast").FeatureStore
        store = feature_store_type(repo_path=str(feast_config.repo_path))
        training_data = store.get_historical_features(
            entity_df=entity_df,
            features=list(FEATURE_REFS),
        ).to_df()

        train_frame, test_frame = self._splitter.split(
            training_data, training_config.test_size
        )
        model = RidgeDemandRegressor(alpha=alpha)
        model.fit(
            train_frame.loc[:, list(FEATURE_COLUMNS)],
            train_frame[training_config.target_column],
        )

        predictions = model.predict(test_frame.loc[:, list(FEATURE_COLUMNS)])
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
        mlflow.set_experiment(config.experiment_name)  # pyright: ignore[reportUnknownMemberType]
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
            mlflow.pyfunc.log_model(  # pyright: ignore[reportUnknownMemberType]
                artifact_path="model",
                python_model=pyfunc_model,
                registered_model_name=config.registered_model_name,
            )
