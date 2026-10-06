from datetime import timedelta
from pathlib import Path

import pandas as pd
from feast import FeatureStore

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.data.supervised_dataset import (
    NextHourDemandDatasetBuilder,
)
from nyc_taxi_demand_forecasting.features.feast_materialization import (
    LocalFeastMaterializer,
)
from nyc_taxi_demand_forecasting.features.hourly_demand import (
    HourlyDemandFeatureBuilder,
)


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    trips_path = config.paths.interim_data / "yellow_taxi_trips.parquet"
    NextHourDemandDatasetBuilder().build(
        trips_path, config.features.training_dataset_path
    )
    HourlyDemandFeatureBuilder().build(
        config.features.training_dataset_path,
        config.features.offline_features_path,
    )

    # Apply Feast definitions (recreated locally)
    LocalFeastMaterializer().apply(config.feast.repo_path)

    # Materialize features from offline store into the online SQLite database
    store = FeatureStore(repo_path=str(config.feast.repo_path))
    event_timestamps = pd.read_parquet(
        config.features.offline_features_path, columns=["event_timestamp"]
    )["event_timestamp"]
    if event_timestamps.empty:
        raise ValueError(
            f"Cannot materialize {config.features.offline_features_path}: "
            f"expected at least one feature row"
        )
    # The window follows the built dataset, not the configured months — rows
    # are floored to the hour, so the exclusive end needs one step past max.
    store.materialize(
        event_timestamps.min().to_pydatetime(),
        event_timestamps.max().to_pydatetime() + timedelta(hours=1),
    )
