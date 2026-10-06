from pathlib import Path

from ml_specialization.configuration import CollectionConfig


class TlcYellowTaxiParquetCollector:
    """Collect immutable trip parquet files into local raw storage.

    Stub left for the specialization exercises — calls raise
    NotImplementedError.

    Example:
        TlcYellowTaxiParquetCollector().collect(config, Path("data/raw"))
    """

    def collect(
        self, config: CollectionConfig, output_directory: Path
    ) -> tuple[Path, ...]:
        raise NotImplementedError(
            "TlcYellowTaxiParquetCollector.collect is not implemented"
        )
