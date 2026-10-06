from typing import Any

import pandas as pd
import pytest
from fakes import FakeFeatureStore, FakePyfuncModel
from fastapi.testclient import TestClient
from ml_specialization.inference import api
from ml_specialization.inference.api import app
from pytest_bdd import given, parsers, scenario, then, when


class TestPredictBdd:
    @staticmethod
    @scenario("features/predict.feature", "Successful demand prediction")
    def test_predict_scenario() -> None:
        # Act & Assert are executed via pytest-bdd Gherkin mapping
        pass

    @staticmethod
    @scenario(
        "features/predict.feature",
        "Missing champion model returns service unavailable",
    )
    def test_predict_model_missing_scenario() -> None:
        pass

    @staticmethod
    @scenario(
        "features/predict.feature",
        "Missing online features returns not found",
    )
    def test_predict_features_missing_scenario() -> None:
        pass

    @staticmethod
    @scenario(
        "features/predict.feature",
        "Feature store failure returns a generic server error",
    )
    def test_predict_store_failure_scenario() -> None:
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
        store=store, model=FakePyfuncModel(predictions=[12.5])
    )
    monkeypatch.setattr(api, "_resources", resources)
    return resources


@given("the champion model is promoted and loaded")
def step_model_loaded(serving_resources: api._ServingResources) -> None:
    # Arrange — the injected champion model already returns 12.5
    assert serving_resources.model is not None


@given("the champion model is not loaded")
def step_model_not_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange — registry answered, but no champion is promoted.
    resources = api._ServingResources(
        store=FakeFeatureStore(repo_path="repo"), model=None
    )
    monkeypatch.setattr(api, "_resources", resources)


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


@given("the feature store has no online features")
def step_no_features() -> None:
    # Arrange
    FakeFeatureStore.online_result = pd.DataFrame()


@given("the feature store fails to answer")
def step_store_failure() -> None:
    # Arrange — internals in the error text must not reach the client.
    FakeFeatureStore.online_error = RuntimeError(
        "sqlite:///secret/path.db internal detail"
    )


@when(
    "a request is sent to predict demand for pickup location 142",
    target_fixture="response",
)
def step_send_request(test_client: TestClient) -> Any:
    # Act
    return test_client.get("/predict/142")


@then(parsers.parse("the response status code should be {code:d}"))
def step_status_code(response: Any, code: int) -> None:
    # Assert
    assert response.status_code == code


@then("the predicted demand should be 12.5")
def step_predicted_demand_match(response: Any) -> None:
    # Assert
    assert response.json()["predicted_demand"] == 12.5


@then("the response detail should not expose internals")
def step_detail_hides_internals(response: Any) -> None:
    # Assert — the client sees the generic contract, not the cause.
    detail = response.json()["detail"]
    assert detail == "Failed to retrieve features from the feature store"
    assert "sqlite" not in detail
