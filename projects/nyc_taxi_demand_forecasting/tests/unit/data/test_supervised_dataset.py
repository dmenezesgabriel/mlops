from pathlib import Path

import pandas as pd
from fakes import trips_frame
from nyc_taxi_demand_forecasting.data.supervised_dataset import (
    NextHourDemandDatasetBuilder,
)


def test_supervised_dataset_builder_creates_next_hour_target() -> None:
    # Arrange
    trips = pd.DataFrame(
        {
            "tpep_pickup_datetime": [
                "2023-01-01 00:05:00",
                "2023-01-01 01:05:00",
                "2023-01-01 01:10:00",
            ],
            "PULocationID": [1, 1, 1],
        }
    )

    # Act
    dataset = NextHourDemandDatasetBuilder().build_from_trips(trips)

    # Assert
    assert dataset.loc[0, "pickup_count"] == 1
    assert dataset.loc[0, "next_hour_pickup_count"] == 2


def test_builder_writes_dataset_parquet(tmp_path: Path) -> None:
    # Arrange
    trips_path = tmp_path / "trips.parquet"
    trips_frame().to_parquet(trips_path, index=False)

    # Act
    output_path = NextHourDemandDatasetBuilder().build(
        trips_path, tmp_path / "processed" / "dataset.parquet"
    )

    # Assert
    dataset = pd.read_parquet(output_path)
    assert "next_hour_pickup_count" in dataset.columns


def test_build_from_trips_drops_row_whose_next_hour_is_unobserved() -> None:
    # Arrange — pickups at hours 0, 1, 3; hour 2 was never observed, so the
    # hour-1 row has no verifiable next-hour label (idle hour vs uncollected
    # data are indistinguishable from the frame) and must be dropped, not
    # labeled with hour-3's count.
    trips = pd.DataFrame(
        {
            "tpep_pickup_datetime": [
                "2023-01-01 00:05:00",
                "2023-01-01 00:10:00",
                "2023-01-01 01:05:00",
                "2023-01-01 03:05:00",
            ],
            "PULocationID": [1, 1, 1, 1],
        }
    )

    # Act
    dataset = NextHourDemandDatasetBuilder().build_from_trips(trips)

    # Assert
    assert list(dataset["pickup_hour"]) == [
        pd.Timestamp("2023-01-01 00:00:00")
    ]
    assert dataset.loc[0, "next_hour_pickup_count"] == 1


def test_build_from_trips_drops_gap_rows_per_location() -> None:
    # Arrange — the drop is per location: loc2's contiguous pair survives
    # while loc1's pre-gap row does not.
    trips = pd.DataFrame(
        {
            "tpep_pickup_datetime": [
                "2023-01-01 00:05:00",
                "2023-01-01 02:05:00",
                "2023-01-01 00:05:00",
                "2023-01-01 01:05:00",
            ],
            "PULocationID": [1, 1, 2, 2],
        }
    )

    # Act
    dataset = NextHourDemandDatasetBuilder().build_from_trips(trips)

    # Assert
    assert list(dataset["pickup_location_id"]) == [2]
    assert dataset.loc[0, "pickup_count"] == 1
    assert dataset.loc[0, "next_hour_pickup_count"] == 1
