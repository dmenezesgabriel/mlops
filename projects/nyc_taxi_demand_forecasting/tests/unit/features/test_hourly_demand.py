import pandas as pd
from nyc_taxi_demand_forecasting.features.hourly_demand import (
    HourlyDemandFeatureBuilder,
)


def test_hourly_demand_feature_builder_renames_event_timestamp() -> None:
    # Arrange
    dataset = pd.DataFrame(
        {
            "pickup_location_id": [1],
            "pickup_hour": [pd.Timestamp("2023-01-01 00:00:00")],
            "pickup_count": [3],
            "hour": [0],
            "day_of_week": [6],
            "is_weekend": [True],
            "month": [1],
        }
    )

    # Act
    features = HourlyDemandFeatureBuilder().build_from_dataset(dataset)

    # Assert
    assert "event_timestamp" in features.columns
    assert features.loc[0, "pickup_count"] == 3
