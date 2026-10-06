from typing import Any

import pandas as pd
import pytest
from fakes import FakeFeatureStore, FakePyfuncModel
from fastapi.testclient import TestClient
from nyc_taxi_demand_forecasting.inference import api
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
def serving_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> api._ServingResources:
    store = FakeFeatureStore(repo_path="repo")
    resources = api._ServingResources(
        store=store,
        model=FakePyfuncModel(predictions=[12.5], as_ndarray=True),
    )
    monkeypatch.setattr(api, "_resources", resources)
    return resources


@given("the champion model is promoted and loaded")
def step_model_loaded(serving_resources: api._ServingResources) -> None:
    # Arrange — the injected champion model already returns 12.5
    assert serving_resources.model is not None


@given("online features exist for pickup location 142")
def step_features_exist() -> None:
    # Arrange
    FakeFeatureStore.online_result = pd.DataFrame(
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
