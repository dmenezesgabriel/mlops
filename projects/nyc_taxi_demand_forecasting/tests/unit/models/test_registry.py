import pytest
from fakes import FakeMlflowClient, FakeModelVersion
from mlflow.exceptions import MlflowException
from nyc_taxi_demand_forecasting.models.registry import (
    latest_model_version,
)


def test_latest_model_version_returns_highest_version() -> None:
    # Arrange — version numbers are strings; a lexicographic max would
    # pick "9" over "10".
    client = FakeMlflowClient(
        versions={
            "model": [
                FakeModelVersion("9"),
                FakeModelVersion("10"),
                FakeModelVersion("2"),
            ]
        }
    )

    # Act
    version = latest_model_version(client, "model")

    # Assert
    assert version == "10"
    assert client.search_calls == ["name='model'"]


def test_latest_model_version_rejects_missing_model() -> None:
    # Arrange — an absent or versionless registration searches to an
    # empty page; either way there is nothing to load.
    client = FakeMlflowClient(versions={})

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
        latest_model_version(client, "model")


def test_latest_model_version_scopes_versions_to_model_name() -> None:
    # Arrange — versions registered under "model" must not answer a
    # search naming a different model; the real client returns an empty
    # page for unregistered names.
    client = FakeMlflowClient(versions={"model": [FakeModelVersion("9")]})

    # Act / Assert
    with pytest.raises(ValueError, match="No registered model found"):
        latest_model_version(client, "other")


def test_fake_client_rejects_writes_to_unregistered_model() -> None:
    # Arrange — the real registry raises RESOURCE_DOES_NOT_EXIST when a
    # write names an unregistered model or an unknown version.
    client = FakeMlflowClient(versions={"model": [FakeModelVersion("7")]})

    # Act / Assert
    with pytest.raises(MlflowException, match="registered model"):
        client.set_model_version_tag("ghost", "1", "evaluated", "true")
    with pytest.raises(MlflowException, match="registered model"):
        client.set_registered_model_alias("ghost", "champion", "1")
    with pytest.raises(MlflowException, match="version"):
        client.set_registered_model_alias("model", "champion", "99")


def test_fake_client_rejects_unknown_search_filter() -> None:
    # Arrange — the fake understands only the name='<model>' filter the
    # pipeline sends; anything else is a test-authoring error, not a miss.
    client = FakeMlflowClient(versions={})

    # Act / Assert
    with pytest.raises(ValueError, match="Unsupported search filter"):
        client.search_model_versions("version='9'")
