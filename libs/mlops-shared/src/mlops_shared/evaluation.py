from collections.abc import Iterable
from dataclasses import dataclass
from math import fsum, sqrt
from typing import Protocol


class RegressionMetricThresholds(Protocol):
    @property
    def max_mae(self) -> float: ...

    @property
    def max_rmse(self) -> float: ...


@dataclass(frozen=True)
class RegressionMetrics:
    mae: float
    rmse: float
    r2: float

    def require_within(self, thresholds: RegressionMetricThresholds) -> None:
        if self.mae > thresholds.max_mae:
            raise ValueError(
                f"Invalid MAE {self.mae}: expected <= {thresholds.max_mae}"
            )
        if self.rmse > thresholds.max_rmse:
            raise ValueError(
                f"Invalid RMSE {self.rmse}: expected <= {thresholds.max_rmse}"
            )


class RegressionMetricCalculator:
    """Calculate dependency-free regression metrics for forecast quality gates.

    Example:
        RegressionMetricCalculator().calculate([1.0, 2.0], [1.0, 3.0])
    """

    def calculate(
        self, actual: Iterable[float], predicted: Iterable[float]
    ) -> RegressionMetrics:
        actual_values = tuple(float(value) for value in actual)
        predicted_values = tuple(float(value) for value in predicted)
        self._require_same_length(actual_values, predicted_values)
        residuals = tuple(
            actual_value - predicted_value
            for actual_value, predicted_value in zip(
                actual_values, predicted_values, strict=True
            )
        )
        return RegressionMetrics(
            mae=self._mean_absolute_error(residuals),
            rmse=self._root_mean_squared_error(residuals),
            r2=self._r2(actual_values, residuals),
        )

    def _require_same_length(
        self, actual: tuple[float, ...], predicted: tuple[float, ...]
    ) -> None:
        if actual and len(actual) == len(predicted):
            return

        raise ValueError(
            f"Invalid regression inputs actual={len(actual)} predicted={len(predicted)}: "
            "expected non-empty iterables with the same length"
        )

    def _mean_absolute_error(self, residuals: tuple[float, ...]) -> float:
        return fsum(abs(residual) for residual in residuals) / len(residuals)

    def _root_mean_squared_error(self, residuals: tuple[float, ...]) -> float:
        return sqrt(
            fsum(residual * residual for residual in residuals)
            / len(residuals)
        )

    def _r2(
        self, actual: tuple[float, ...], residuals: tuple[float, ...]
    ) -> float:
        actual_mean = fsum(actual) / len(actual)
        total_sum_squares = fsum(
            (actual_value - actual_mean) ** 2 for actual_value in actual
        )
        if total_sum_squares == 0:
            return 0.0

        residual_sum_squares = fsum(
            residual * residual for residual in residuals
        )
        return 1 - residual_sum_squares / total_sum_squares
