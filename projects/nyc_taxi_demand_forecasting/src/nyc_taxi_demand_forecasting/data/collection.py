from pathlib import Path

import requests

from nyc_taxi_demand_forecasting.configuration import CollectionConfig


class TlcYellowTaxiParquetCollector:
    """Collect immutable TLC parquet files into local raw storage.

    Example:
        collector.collect(config, Path("data/raw"))
    """

    def collect(
        self, config: CollectionConfig, output_directory: Path
    ) -> tuple[Path, ...]:
        output_directory.mkdir(parents=True, exist_ok=True)
        return tuple(
            self._download_month(config, month, output_directory)
            for month in config.months
        )

    def _download_month(
        self, config: CollectionConfig, month: int, output_directory: Path
    ) -> Path:
        file_name = (
            f"{config.taxi_type}_tripdata_{config.year}-{month:02d}.parquet"
        )
        output_path = output_directory / file_name
        if output_path.exists():
            return output_path

        response = requests.get(config.source_url(month), timeout=60)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
