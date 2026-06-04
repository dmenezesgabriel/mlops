from pathlib import Path

import pandas as pd

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.tuning import DemandModelTuner


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    dataset = pd.read_parquet(config.features.training_dataset_path)
    DemandModelTuner().select_best(dataset, config.training.target_column)
