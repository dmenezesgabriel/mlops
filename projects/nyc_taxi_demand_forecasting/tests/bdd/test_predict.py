from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from nyc_taxi_demand_forecasting.inference.api import app
from pytest_bdd import given, scenario, then, when


class TestPredictBdd:
    @staticmethod
    @scenario("features/predict.feature", "Successful demand prediction")
    def test_predict_scenario() -> None:
        # Act & Assert are executed via pytest-bdd Gherkin mapping
        pass


# --- Step Definitions (pytest-bdd resolves fixture dependencies automatically) ---


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_fetch() -> Iterator[MagicMock]:
    with patch(
        "nyc_taxi_demand_forecasting.inference.api.fetch_online_features"
    ) as mock:
        yield mock


@pytest.fixture
def mock_model() -> Iterator[MagicMock]:
    with patch("nyc_taxi_demand_forecasting.inference.api._model") as mock:
        yield mock


@given("the champion model is promoted and loaded")
def step_model_loaded(mock_model: MagicMock) -> None:
    # Arrange
    mock_model.predict.return_value = pd.Series([12.5])


@given("online features exist for pickup location 142")
def step_features_exist(mock_fetch: MagicMock) -> None:
    # Arrange
    mock_fetch.return_value = pd.DataFrame(
        [
            {
                "pickup_count": 10,
                "hour": 8,
                "day_of_week": 1,
                "is_weekend": False,
                "month": 1,
            }
        ]
    )


@when(
    "a request is sent to predict demand for pickup location 142",
    target_fixture="response",
)
def step_send_request(test_client: TestClient) -> Any:
    # Act
    return test_client.get("/predict/142")


@then("the response status code should be 200")
def step_status_code_200(response: Any) -> None:
    # Assert
    assert response.status_code == 200


@then("the predicted demand should be 12.5")
def step_predicted_demand_match(response: Any) -> None:
    # Assert
    assert response.json()["predicted_demand"] == 12.5
