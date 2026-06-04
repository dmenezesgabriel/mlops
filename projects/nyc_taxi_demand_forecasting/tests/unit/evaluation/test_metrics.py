import pandas as pd
from nyc_taxi_demand_forecasting.evaluation.metrics import RegressionMetricCalculator


def test_regression_metric_calculator_computes_errors() -> None:
    # Arrange
    actual = pd.Series([1.0, 2.0, 3.0])
    predicted = pd.Series([1.0, 2.0, 2.0])

    # Act
    metrics = RegressionMetricCalculator().calculate(actual, predicted)

    # Assert
    assert metrics.mae == 1 / 3
    assert round(metrics.rmse, 6) == 0.57735
