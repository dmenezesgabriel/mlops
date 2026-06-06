import calendar
from datetime import datetime, timedelta
from pathlib import Path

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
    year = config.collection.year
    months = config.collection.months
    start_date = datetime(year, min(months), 1)
    last_day = calendar.monthrange(year, max(months))[1]
    end_date = datetime(year, max(months), last_day) + timedelta(days=1)

    store.materialize(start_date, end_date)
