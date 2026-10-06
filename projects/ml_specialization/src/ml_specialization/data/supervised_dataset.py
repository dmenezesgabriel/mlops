from pathlib import Path


class NextHourDemandDatasetBuilder:
    """Build a supervised next-hour demand dataset from hourly trip records.

    Stub left for the specialization exercises — calls raise
    NotImplementedError.

    Example:
        NextHourDemandDatasetBuilder().build(trips_path, dataset_path)
    """

    def build(self, trips_path: Path, output_path: Path) -> Path:
        raise NotImplementedError(
            "NextHourDemandDatasetBuilder.build is not implemented"
        )
