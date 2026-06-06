import pandas as pd
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
