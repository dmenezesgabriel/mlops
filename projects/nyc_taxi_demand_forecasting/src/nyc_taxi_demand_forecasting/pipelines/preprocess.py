from pathlib import Path

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.data.preprocessing import YellowTaxiTripPreprocessor


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)
    YellowTaxiTripPreprocessor().preprocess(config.paths.raw_data, config.paths.interim_data)
