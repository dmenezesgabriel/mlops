import logging
from pathlib import Path

import pandas as pd
import pytest
from fakes import trips_frame
from nyc_taxi_demand_forecasting.configuration import CollectionConfig
from nyc_taxi_demand_forecasting.data.preprocessing import (
    YellowTaxiTripPreprocessor,
)


def _collection_config(months: tuple[int, ...] = (1, 3)) -> CollectionConfig:
    return CollectionConfig(
        year=2023,
        months=months,
        taxi_type="yellow",
        source_url_template=(
            "https://example.test/{taxi_type}_{year}-{month:02d}.parquet"
        ),
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


def test_clean_applies_boundary_filters() -> None:
    # Arrange — boundary values: a zero-duration trip (0 is not > 0) and a
    # zero-id location trip are invalid; a zero-distance trip is legal.
    trips = pd.DataFrame(
        {
            "tpep_pickup_datetime": [
                "2023-01-01 00:00:00",
                "2023-01-01 01:00:00",
                "2023-01-01 02:00:00",
                "2023-01-01 03:00:00",
            ],
            "tpep_dropoff_datetime": [
                "2023-01-01 00:10:00",
                "2023-01-01 01:00:00",
                "2023-01-01 02:20:00",
                "2023-01-01 03:30:00",
            ],
            "PULocationID": [1, 1, 0, 1],
            "DOLocationID": [2, 2, 2, 2],
            "passenger_count": [1, 1, 1, 1],
            "trip_distance": [1.0, 1.0, 1.0, 0.0],
            "fare_amount": [8.0, 9.0, 8.0, 8.0],
        }
    )

    # Act
    cleaned_trips = YellowTaxiTripPreprocessor().clean(trips)

    # Assert — only the valid trip and the zero-distance trip survive.
    assert cleaned_trips["duration_minutes"].to_list() == [10, 30]
    assert cleaned_trips["trip_distance"].to_list() == [1.0, 0.0]


def test_preprocess_writes_cleaned_parquet(tmp_path: Path) -> None:
    # Arrange
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    trips = trips_frame()
    trips.iloc[:1].to_parquet(
        raw_directory / "yellow_tripdata_2023-01.parquet", index=False
    )
    trips.iloc[1:].to_parquet(
        raw_directory / "yellow_tripdata_2023-03.parquet", index=False
    )

    # Act
    output_path = YellowTaxiTripPreprocessor().preprocess(
        raw_directory, tmp_path / "interim", _collection_config()
    )

    # Assert
    assert output_path.name == "yellow_taxi_trips.parquet"
    assert len(pd.read_parquet(output_path)) == 2


def test_preprocess_reads_only_configured_months(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange — a stray month-2 file must not contaminate a month-1 build
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    trips = trips_frame()
    trips.iloc[:1].to_parquet(
        raw_directory / "yellow_tripdata_2023-01.parquet", index=False
    )
    stray = trips.iloc[1:].copy()
    stray["tpep_pickup_datetime"] = pd.to_datetime("2023-02-01 00:05:00")
    stray["tpep_dropoff_datetime"] = pd.to_datetime("2023-02-01 00:20:00")
    stray.to_parquet(
        raw_directory / "yellow_tripdata_2023-02.parquet", index=False
    )

    # Act
    with caplog.at_level(logging.WARNING):
        output_path = YellowTaxiTripPreprocessor().preprocess(
            raw_directory, tmp_path / "interim", _collection_config((1,))
        )

    # Assert
    interim = pd.read_parquet(output_path)
    assert len(interim) == 1
    assert interim["tpep_pickup_datetime"].dt.month.unique().tolist() == [1]
    warnings = [
        record
        for record in caplog.records
        if record.msg == "unconfigured_raw_parquet_ignored"
    ]
    assert len(warnings) == 1
    assert warnings[0].files == ["yellow_tripdata_2023-02.parquet"]


def test_preprocess_raises_on_missing_configured_month(
    tmp_path: Path,
) -> None:
    # Arrange — months (1, 3) configured but only month-1 collected
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()
    trips_frame().to_parquet(
        raw_directory / "yellow_tripdata_2023-01.parquet", index=False
    )

    # Act / Assert
    with pytest.raises(
        FileNotFoundError, match="yellow_tripdata_2023-03.parquet"
    ):
        YellowTaxiTripPreprocessor().preprocess(
            raw_directory, tmp_path / "interim", _collection_config()
        )


def test_preprocess_requires_raw_parquet_files(tmp_path: Path) -> None:
    # Arrange
    raw_directory = tmp_path / "raw"
    raw_directory.mkdir()

    # Act / Assert
    with pytest.raises(FileNotFoundError, match="Missing raw parquet files"):
        YellowTaxiTripPreprocessor().preprocess(
            raw_directory, tmp_path / "interim", _collection_config()
        )
