from pathlib import Path
from typing import Protocol, TypeVar

LoadedDatasetType = TypeVar("LoadedDatasetType", covariant=True)
WrittenDatasetType = TypeVar("WrittenDatasetType", contravariant=True)


class DatasetLoader(Protocol[LoadedDatasetType]):
    """Load a dataset from a stable storage boundary.

    Example:
        rows = loader.load(Path("data/processed/training.parquet"))
    """

    def load(self, dataset_path: Path) -> LoadedDatasetType:
        pass


class DatasetWriter(Protocol[WrittenDatasetType]):
    """Write a dataset through a stable storage boundary.

    Example:
        writer.write(rows, Path("data/processed/training.parquet"))
    """

    def write(self, dataset: WrittenDatasetType, dataset_path: Path) -> None:
        pass
