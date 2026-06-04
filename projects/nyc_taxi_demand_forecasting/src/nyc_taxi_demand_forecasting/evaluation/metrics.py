from dataclasses import dataclass

import numpy as np
import pandas as pd

from nyc_taxi_demand_forecasting.configuration import EvaluationConfig


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float

    def validate(self, config: EvaluationConfig) -> None:
        if self.mae > config.max_mae:
            raise ValueError(f"Invalid MAE {self.mae}: expected <= {config.max_mae}")
        if self.rmse > config.max_rmse:
            raise ValueError(f"Invalid RMSE {self.rmse}: expected <= {config.max_rmse}")


class RegressionMetricCalculator:
    """Calculate regression metrics for demand forecasts.

    Example:
        RegressionMetricCalculator().calculate(actual, predicted)
    """

    def calculate(self, actual: pd.Series, predicted: pd.Series) -> RegressionMetrics:
        residuals = actual.astype(float) - predicted.astype(float)
        mae = float(residuals.abs().mean())
        rmse = float(np.sqrt(np.square(residuals).mean()))
        return RegressionMetrics(mae=mae, rmse=rmse, r2=self._r2(actual, residuals))

    def _r2(self, actual: pd.Series, residuals: pd.Series) -> float:
        total_sum_squares = float(
            np.square(actual.astype(float) - actual.astype(float).mean()).sum()
        )
        if total_sum_squares == 0:
            return 0.0

        residual_sum_squares = float(np.square(residuals).sum())
        return 1 - residual_sum_squares / total_sum_squares
