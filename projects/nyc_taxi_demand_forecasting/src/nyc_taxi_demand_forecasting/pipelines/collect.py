from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.data.collection import TlcYellowTaxiParquetCollector


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    TlcYellowTaxiParquetCollector().collect(config.collection, config.paths.raw_data)
