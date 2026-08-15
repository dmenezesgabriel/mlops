from pathlib import Path

from {{ cookiecutter.project_slug }}.configuration import CollectionConfig


class TlcYellowTaxiParquetCollector:
    """Collect immutable trip parquet files into local raw storage.

    Example:
        TlcYellowTaxiParquetCollector().collect(config, Path("data/raw"))
    """

    def collect(
        self, config: CollectionConfig, output_directory: Path
    ) -> tuple[Path, ...]:
        output_directory.mkdir(parents=True, exist_ok=True)
        return tuple(
            output_directory
            / f"{config.taxi_type}_tripdata_{config.year}-{month:02d}.parquet"
            for month in config.months
        )
