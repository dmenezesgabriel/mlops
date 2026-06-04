import logging
from pathlib import Path

import pandas as pd
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.training import DemandDatasetSplitter, LinearDemandRegressor


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    dataset = pd.read_parquet(config.features.training_dataset_path)
    train_frame, test_frame = DemandDatasetSplitter().split(dataset, config.training.test_size)
    feature_columns = ["pickup_count", "hour", "day_of_week", "is_weekend", "month"]
    model = LinearDemandRegressor().fit(
        train_frame.loc[:, feature_columns], train_frame[config.training.target_column]
    )
    predictions = model.predict(test_frame.loc[:, feature_columns])
    metrics = RegressionMetricCalculator().calculate(
        test_frame[config.training.target_column], predictions
    )
    logging.getLogger(__name__).info(
        "model_evaluation_completed",
        extra={"mae": metrics.mae, "rmse": metrics.rmse, "r2": metrics.r2},
    )
    metrics.require_within(config.evaluation)
