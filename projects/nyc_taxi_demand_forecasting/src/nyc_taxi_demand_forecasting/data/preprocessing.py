from pathlib import Path

import pandas as pd


class YellowTaxiTripPreprocessor:
    """Clean raw yellow taxi trips into canonical interim parquet files.

    Example:
        YellowTaxiTripPreprocessor().preprocess(raw_dir, interim_dir)
    """

    _columns = (
        "tpep_pickup_datetime",
        "tpep_dropoff_datetime",
        "PULocationID",
        "DOLocationID",
        "passenger_count",
        "trip_distance",
        "fare_amount",
    )

    def preprocess(self, raw_directory: Path, output_directory: Path) -> Path:
        output_directory.mkdir(parents=True, exist_ok=True)
        trips = pd.concat(
            self._read_raw_files(raw_directory), ignore_index=True
        )
        cleaned_trips = self.clean(trips)
        output_path = output_directory / "yellow_taxi_trips.parquet"
        cleaned_trips.to_parquet(output_path, index=False)
        return output_path

    def clean(self, trips: pd.DataFrame) -> pd.DataFrame:
        selected_trips = trips.loc[:, list(self._columns)].copy()
        selected_trips["duration_minutes"] = self._duration_minutes(
            selected_trips
        )
        valid_trips = selected_trips[selected_trips["duration_minutes"] > 0]
        valid_trips = valid_trips[valid_trips["PULocationID"] > 0]
        return valid_trips[valid_trips["trip_distance"] >= 0].reset_index(
            drop=True
        )

    def _read_raw_files(self, raw_directory: Path) -> list[pd.DataFrame]:
        parquet_paths = sorted(raw_directory.glob("*.parquet"))
        if parquet_paths:
            return [
                pd.read_parquet(path, columns=list(self._columns))
                for path in parquet_paths
            ]

        raise FileNotFoundError(
            f"Missing raw parquet files in {raw_directory}: expected *.parquet"
        )

    def _duration_minutes(self, trips: pd.DataFrame) -> pd.Series:
        pickup_time = pd.to_datetime(trips["tpep_pickup_datetime"])
        dropoff_time = pd.to_datetime(trips["tpep_dropoff_datetime"])
        return (dropoff_time - pickup_time).dt.total_seconds() / 60
