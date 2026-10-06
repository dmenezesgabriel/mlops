import importlib
import logging
import sys
from unittest.mock import patch

import ml_specialization.inference.api as api
import pandas as pd
import pytest
from fakes import (
    FakeFeastModule,
    FakeFeatureStore,
    FakeMlflowModule,
    FakePyfuncModel,
)
from fastapi.testclient import TestClient
from ml_specialization.inference.api import app
from mlflow.exceptions import MlflowException

_API_LOGGER = "ml_specialization.inference.api"


def _features_frame() -> pd.DataFrame:
    return pd.DataFrame(
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


def _inject_resources(
    monkeypatch: pytest.MonkeyPatch, model: FakePyfuncModel | None
) -> FakeFeatureStore:
    store = FakeFeatureStore(repo_path="repo")
    monkeypatch.setattr(
        api,
        "_resources",
        api._ServingResources(store=store, model=model),
    )
    return store


def _fake_boundaries(
    monkeypatch: pytest.MonkeyPatch, fake_mlflow: FakeMlflowModule
) -> None:
    monkeypatch.setattr(api, "mlflow", fake_mlflow)
    monkeypatch.setattr(api, "FeatureStore", FakeFeatureStore)
    monkeypatch.setattr(api, "_resources", None)


def test_import_does_not_load_model_or_store() -> None:
    # Arrange — faked boundary modules let a module-body re-run be observed.
    fake_mlflow = FakeMlflowModule()

    # Act — re-executing the module under the fakes.
    with patch.dict(
        sys.modules, {"mlflow": fake_mlflow, "feast": FakeFeastModule()}
    ):
        importlib.reload(api)
    importlib.reload(api)

    # Assert — import alone must not touch the store, tracker, or registry.
    assert fake_mlflow.pyfunc.loaded_uris == []
    assert fake_mlflow.tracking_uri is None
    assert FakeFeatureStore.instances == []


def test_resources_load_once_on_first_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    _fake_boundaries(monkeypatch, fake_mlflow)

    # Act
    first = api._serving_resources()
    second = api._serving_resources()

    # Assert — one lazy build, reused afterwards.
    assert first is second
    assert len(FakeFeatureStore.instances) == 1
    assert fake_mlflow.pyfunc.loaded_uris == [
        "models:/ml_specialization_forecaster@champion"
    ]
    assert fake_mlflow.tracking_uri is not None
    assert fake_mlflow.tracking_uri.endswith("ml_specialization/mlflow.db")


def test_model_load_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — a non-registry failure must surface, not hide behind a 503.
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.load_error = RuntimeError("SENTINEL_BREAKAGE")
    _fake_boundaries(monkeypatch, fake_mlflow)
    client = TestClient(app)

    # Act & Assert
    with pytest.raises(RuntimeError, match="SENTINEL_BREAKAGE"):
        client.get("/predict/142")


def test_missing_champion_returns_503_and_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange — registry-level miss: logged once, then a fast 503 contract.
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.load_error = MlflowException(
        "Registered Model with name=ml_specialization_forecaster not found"
    )
    _fake_boundaries(monkeypatch, fake_mlflow)
    client = TestClient(app)

    # Act
    with caplog.at_level(logging.ERROR, logger=_API_LOGGER):
        response = client.get("/predict/142")
        retry = client.get("/predict/142")

    # Assert
    assert response.status_code == 503
    assert retry.status_code == 503
    assert response.json()["detail"] == (
        "Model is not loaded. Ensure champion model is promoted in MLflow."
    )
    assert any(
        record.getMessage() == "champion_model_load_failed"
        and record.exc_info is not None
        for record in caplog.records
    )
    assert fake_mlflow.pyfunc.loaded_uris == [
        "models:/ml_specialization_forecaster@champion"
    ]


def test_predict_returns_prediction(monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange
    model = FakePyfuncModel(predictions=[12.5])
    store = _inject_resources(monkeypatch, model)
    FakeFeatureStore.online_result = _features_frame()
    client = TestClient(app)

    # Act
    response = client.get("/predict/142")

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "pickup_location_id": 142,
        "features": {
            "pickup_count": 10,
            "hour": 8,
            "day_of_week": 1,
            "is_weekend": False,
            "month": 1,
        },
        "predicted_demand": 12.5,
    }
    assert store.online_calls == [
        (
            [
                "hourly_pickup_demand:pickup_count",
                "hourly_pickup_demand:hour",
                "hourly_pickup_demand:day_of_week",
                "hourly_pickup_demand:is_weekend",
                "hourly_pickup_demand:month",
            ],
            [{"pickup_location_id": 142}],
        )
    ]
    assert len(model.predicted_frames) == 1


def test_predict_returns_503_when_model_not_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    _inject_resources(monkeypatch, model=None)
    client = TestClient(app)

    # Act
    response = client.get("/predict/142")

    # Assert
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Model is not loaded. Ensure champion model is promoted in MLflow."
    )


def test_predict_returns_404_when_features_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — store answers with an empty frame.
    _inject_resources(monkeypatch, FakePyfuncModel(predictions=[12.5]))
    FakeFeatureStore.online_result = pd.DataFrame()
    client = TestClient(app)

    # Act
    response = client.get("/predict/142")

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No online features found for location ID 142"
    )


def test_predict_returns_404_when_pickup_count_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — store answers, but the frame lacks the pickup_count column.
    _inject_resources(monkeypatch, FakePyfuncModel(predictions=[12.5]))
    FakeFeatureStore.online_result = pd.DataFrame(
        [{"hour": 8, "day_of_week": 1, "is_weekend": False, "month": 1}]
    )
    client = TestClient(app)

    # Act
    response = client.get("/predict/142")

    # Assert — an incomplete frame takes the 404 contract, not a raw 500.
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No online features found for location ID 142"
    )


def test_predict_returns_404_when_pickup_count_is_na(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — a row exists but its pickup_count cell is null.
    _inject_resources(monkeypatch, FakePyfuncModel(predictions=[12.5]))
    frame = _features_frame()
    frame["pickup_count"] = pd.NA
    FakeFeatureStore.online_result = frame
    client = TestClient(app)

    # Act
    response = client.get("/predict/142")

    # Assert — a null cell takes the 404 contract, not a raw 500.
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No online features found for location ID 142"
    )


def test_predict_returns_generic_500_and_logs_fetch_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange — internals in the exception text must not reach the client.
    _inject_resources(monkeypatch, FakePyfuncModel(predictions=[12.5]))
    FakeFeatureStore.online_error = RuntimeError(
        "sqlite:///secret/path.db internal detail"
    )
    client = TestClient(app)

    # Act
    with caplog.at_level(logging.ERROR, logger=_API_LOGGER):
        response = client.get("/predict/142")

    # Assert
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == "Failed to retrieve features from the feature store"
    assert "sqlite" not in detail
    assert any(
        record.getMessage() == "online_feature_fetch_failed"
        and record.exc_info is not None
        for record in caplog.records
    )


def test_fetch_online_features_requests_all_feature_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    store = _inject_resources(monkeypatch, model=None)
    FakeFeatureStore.online_result = _features_frame()

    # Act
    features = api.fetch_online_features(142)

    # Assert
    assert features is FakeFeatureStore.online_result
    assert store.online_calls[0][0] == [
        f"hourly_pickup_demand:{name}"
        for name in [
            "pickup_count",
            "hour",
            "day_of_week",
            "is_weekend",
            "month",
        ]
    ]
