from pathlib import Path

from {{ cookiecutter.project_slug }}.configuration import CollectionConfig


class TlcYellowTaxiParquetCollector:
    """Collect immutable trip parquet files into local raw storage.

    Scaffolded stub — calls raise NotImplementedError.

    Example:
        TlcYellowTaxiParquetCollector().collect(config, Path("data/raw"))
    """

    def collect(
        self, config: CollectionConfig, output_directory: Path
    ) -> tuple[Path, ...]:
        raise NotImplementedError(
            "TlcYellowTaxiParquetCollector.collect is not implemented"
        )
