from dataclasses import dataclass

import pytest
from mlops_shared.evaluation import RegressionMetricCalculator


@dataclass(frozen=True)
class StrictRegressionThresholds:
    max_mae: float
    max_rmse: float


def test_regression_metric_calculator_computes_errors() -> None:
    # Arrange
    actual = [1.0, 2.0, 3.0]
    predicted = [1.0, 2.0, 2.0]

    # Act
    metrics = RegressionMetricCalculator().calculate(actual, predicted)

    # Assert
    assert metrics.mae == 1 / 3
    assert round(metrics.rmse, 6) == 0.57735


def test_regression_metrics_reject_values_outside_thresholds() -> None:
    # Arrange
    metrics = RegressionMetricCalculator().calculate([1.0, 3.0], [1.0, 1.0])
    thresholds = StrictRegressionThresholds(max_mae=0.5, max_rmse=2.0)

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid MAE"):
        metrics.require_within(thresholds)


def test_regression_metric_calculator_rejects_empty_inputs() -> None:
    # Arrange
    calculator = RegressionMetricCalculator()

    # Act / Assert
    with pytest.raises(ValueError, match="expected non-empty iterables"):
        calculator.calculate([], [])
