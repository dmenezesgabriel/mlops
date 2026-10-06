import logging
from pathlib import Path

import pandas as pd

from nyc_taxi_demand_forecasting.configuration import CollectionConfig


class YellowTaxiTripPreprocessor:
    """Clean raw yellow taxi trips into canonical interim parquet files.

    Example:
        YellowTaxiTripPreprocessor().preprocess(raw_dir, interim_dir, collection)
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

    def preprocess(
        self,
        raw_directory: Path,
        output_directory: Path,
        collection: CollectionConfig,
    ) -> Path:
        output_directory.mkdir(parents=True, exist_ok=True)
        trips = pd.concat(
            self._read_raw_files(raw_directory, collection),
            ignore_index=True,
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

    def _read_raw_files(
        self, raw_directory: Path, collection: CollectionConfig
    ) -> list[pd.DataFrame]:
        file_names = collection.file_names()
        missing_names = [
            name for name in file_names if not (raw_directory / name).is_file()
        ]
        if missing_names:
            raise FileNotFoundError(
                f"Missing raw parquet files in {raw_directory}: "
                f"expected {missing_names}"
            )
        self._warn_on_extras(raw_directory, file_names)
        return [
            pd.read_parquet(raw_directory / name, columns=list(self._columns))
            for name in file_names
        ]

    def _warn_on_extras(
        self, raw_directory: Path, file_names: tuple[str, ...]
    ) -> None:
        extra_names = sorted(
            path.name
            for path in raw_directory.glob("*.parquet")
            if path.name not in file_names
        )
        if not extra_names:
            return
        # A stray file would otherwise vanish silently at materialize time —
        # the online store only sees the configured window.
        logging.getLogger(__name__).warning(
            "unconfigured_raw_parquet_ignored",
            extra={"files": extra_names},
        )

    def _duration_minutes(self, trips: pd.DataFrame) -> pd.Series:
        pickup_time = pd.to_datetime(trips["tpep_pickup_datetime"])
        dropoff_time = pd.to_datetime(trips["tpep_dropoff_datetime"])
        return (dropoff_time - pickup_time).dt.total_seconds() / 60
