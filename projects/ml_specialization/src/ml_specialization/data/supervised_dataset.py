from pathlib import Path

import pandas as pd


class NextHourDemandDatasetBuilder:
    """Build a supervised next-hour demand dataset from hourly trip records.

    Example:
        NextHourDemandDatasetBuilder().build(trips_path, dataset_path)
    """

    def build(self, trips_path: Path, output_path: Path) -> Path:
        trips = pd.read_parquet(trips_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        trips.to_parquet(output_path, index=False)
        return output_path
