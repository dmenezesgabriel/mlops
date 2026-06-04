from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.data.supervised_dataset import NextHourDemandDatasetBuilder
from nyc_taxi_demand_forecasting.features.hourly_demand import HourlyDemandFeatureBuilder


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    trips_path = config.paths.interim_data / "yellow_taxi_trips.parquet"
    NextHourDemandDatasetBuilder().build(trips_path, config.features.training_dataset_path)
    HourlyDemandFeatureBuilder().build(
        config.features.training_dataset_path,
        config.features.offline_features_path,
    )
