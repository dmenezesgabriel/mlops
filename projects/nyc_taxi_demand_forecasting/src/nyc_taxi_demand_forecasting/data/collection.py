import logging
from pathlib import Path

import requests

from nyc_taxi_demand_forecasting.configuration import CollectionConfig

# Parquet frames its payload with a magic word at both ends: a missing
# trailer is exactly what a crashed write or a saved error page looks like.
_PARQUET_MAGIC = b"PAR1"
_MINIMUM_PARQUET_SIZE = 2 * len(_PARQUET_MAGIC)


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
        output_path = output_directory / config.file_name(month)
        if output_path.exists():
            if self._is_cached_parquet(output_path):
                return output_path
            logging.getLogger(__name__).warning(
                "corrupt_cached_parquet_redownload",
                extra={"path": str(output_path)},
            )

        url = config.source_url(month)
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        content = response.content
        if not self._is_parquet_content(content):
            raise ValueError(
                f"Invalid download from {url}: expected parquet "
                f"(PAR1 magic), got {content[:8]!r}"
            )
        self._write_atomically(output_path, content)
        return output_path

    def _is_cached_parquet(self, path: Path) -> bool:
        if not path.is_file() or path.stat().st_size < _MINIMUM_PARQUET_SIZE:
            return False
        with path.open("rb") as file:
            header = file.read(len(_PARQUET_MAGIC))
            file.seek(-len(_PARQUET_MAGIC), 2)
            trailer = file.read(len(_PARQUET_MAGIC))
        return header == _PARQUET_MAGIC and trailer == _PARQUET_MAGIC

    def _is_parquet_content(self, content: bytes) -> bool:
        return (
            len(content) >= _MINIMUM_PARQUET_SIZE
            and content[: len(_PARQUET_MAGIC)] == _PARQUET_MAGIC
            and content[-len(_PARQUET_MAGIC) :] == _PARQUET_MAGIC
        )

    def _write_atomically(self, output_path: Path, content: bytes) -> None:
        temporary_path = output_path.with_suffix(".tmp")
        temporary_path.write_bytes(content)
        temporary_path.replace(output_path)
