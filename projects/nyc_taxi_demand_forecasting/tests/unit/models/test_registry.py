import pytest
from fakes import FakeMlflowClient, FakeModelVersion
from nyc_taxi_demand_forecasting.models.registry import (
    latest_model_version,
)


def test_latest_model_version_returns_highest_version() -> None:
    # Arrange — version numbers are strings; a lexicographic max would
    # pick "9" over "10".
    client = FakeMlflowClient(
        versions=[
            FakeModelVersion("9"),
            FakeModelVersion("10"),
            FakeModelVersion("2"),
        ]
    )

    # Act
    version = latest_model_version(client, "model")

    # Assert
    assert version == "10"
    assert client.search_calls == ["name='model'"]


def test_latest_model_version_rejects_missing_model() -> None:
    # Arrange — an absent or versionless registration searches to an
    # empty page; either way there is nothing to load.
    client = FakeMlflowClient(versions=[])

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
        latest_model_version(client, "model")
