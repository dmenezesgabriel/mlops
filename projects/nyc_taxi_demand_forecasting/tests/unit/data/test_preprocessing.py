from pathlib import Path

import pandas as pd
import pytest
from fakes import trips_frame
from nyc_taxi_demand_forecasting.data.preprocessing import (
    YellowTaxiTripPreprocessor,
)


def test_preprocessor_removes_invalid_trips() -> None:
    # Arrange
    trips = pd.DataFrame(
        {
            "tpep_pickup_datetime": [
                "2023-01-01 00:00:00",
                "2023-01-01 01:00:00",
            ],
            "tpep_dropoff_datetime": [
                "2023-01-01 00:10:00",
                "2023-01-01 00:55:00",
            ],
            "PULocationID": [1, 2],
            "DOLocationID": [2, 3],
            "passenger_count": [1, 1],
            "trip_distance": [1.0, 1.0],
            "fare_amount": [8.0, 9.0],
        }
    )

    # Act
    cleaned_trips = YellowTaxiTripPreprocessor().clean(trips)

    # Assert
    assert len(cleaned_trips) == 1
    assert cleaned_trips.loc[0, "duration_minutes"] == 10


def test_preprocess_writes_cleaned_parquet(tmp_path: Path) -> None:
    # Arrange
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    trips = trips_frame()
    trips.iloc[:1].to_parquet(raw_directory / "a.parquet", index=False)
    trips.iloc[1:].to_parquet(raw_directory / "b.parquet", index=False)

    # Act
    output_path = YellowTaxiTripPreprocessor().preprocess(
        raw_directory, tmp_path / "interim"
    )

    # Assert
    assert output_path.name == "yellow_taxi_trips.parquet"
    assert len(pd.read_parquet(output_path)) == 2


def test_preprocess_requires_raw_parquet_files(tmp_path: Path) -> None:
    # Arrange
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()

    # Act / Assert
    with pytest.raises(FileNotFoundError, match="Missing raw parquet files"):
        YellowTaxiTripPreprocessor().preprocess(
            raw_directory, tmp_path / "interim"
        )
