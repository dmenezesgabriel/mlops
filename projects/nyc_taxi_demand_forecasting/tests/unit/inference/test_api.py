from unittest.mock import MagicMock, patch

import pandas as pd
from fastapi.testclient import TestClient
from nyc_taxi_demand_forecasting.inference.api import app


@patch("nyc_taxi_demand_forecasting.inference.api._model")
@patch("nyc_taxi_demand_forecasting.inference.api.fetch_online_features")
def test_predict_returns_prediction(
    mock_fetch: MagicMock, mock_model: MagicMock
) -> None:
    # Arrange
    client = TestClient(app)

    # Mock online feature return
    features_df = pd.DataFrame(
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
    mock_fetch.return_value = features_df

    # Mock model prediction return
    mock_model.predict.return_value = pd.Series([12.5])

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

    mock_fetch.assert_called_once_with(142)
    mock_model.predict.assert_called_once()


@patch("nyc_taxi_demand_forecasting.inference.api._model", None)
def test_predict_returns_503_when_model_not_loaded() -> None:
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/predict/142")

    # Assert
    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "Model is not loaded. Ensure champion model is promoted in MLflow."
    )


@patch("nyc_taxi_demand_forecasting.inference.api._model")
@patch("nyc_taxi_demand_forecasting.inference.api.fetch_online_features")
def test_predict_returns_404_when_features_not_found(
    mock_fetch: MagicMock, mock_model: MagicMock
) -> None:
    # Arrange
    client = TestClient(app)

    # Mock empty features df
    mock_fetch.return_value = pd.DataFrame()

    # Act
    response = client.get("/predict/142")

    # Assert
    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "No online features found for location ID 142"
    )
