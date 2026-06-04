from pathlib import Path

import pandas as pd

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.evaluation.metrics import RegressionMetricCalculator


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    dataset = pd.read_parquet(config.features.training_dataset_path)
    predictions = pd.Series([dataset[config.training.target_column].median()] * len(dataset))
    metrics = RegressionMetricCalculator().calculate(
        dataset[config.training.target_column], predictions
    )
    metrics.validate(config.evaluation)
