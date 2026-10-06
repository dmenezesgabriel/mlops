"""Re-export seam for the shared regression metrics.

Template parity: the sibling `nyc_taxi_demand_forecasting` project consumes
its twin of this module from `models/training.py`. Kept here so exercises and
`tests/unit/evaluation/test_metrics.py` import a stable local path instead of
reaching into `mlops_shared` directly.
"""

from mlops_shared.evaluation import (
    RegressionMetricCalculator,
    RegressionMetrics,
)

__all__ = ["RegressionMetricCalculator", "RegressionMetrics"]
