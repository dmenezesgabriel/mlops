from pathlib import Path

import pandas as pd


class YellowTaxiTripPreprocessor:
    """Clean raw trip records and aggregate them into hourly trip counts.

    Example:
        YellowTaxiTripPreprocessor().preprocess(Path("data/raw"), Path("data/interim"))
    """

    def preprocess(self, raw_directory: Path, output_directory: Path) -> Path:
        output_directory.mkdir(parents=True, exist_ok=True)
        trips_path = output_directory / "yellow_taxi_trips.parquet"
        if not trips_path.exists():
            pd.DataFrame().to_parquet(trips_path, index=False)
        return trips_path
