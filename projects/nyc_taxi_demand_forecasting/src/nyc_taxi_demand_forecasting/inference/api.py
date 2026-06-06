from pathlib import Path
from typing import Any

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from feast import FeatureStore

from nyc_taxi_demand_forecasting.configuration import (
    ProjectConfig,
    ProjectConfigLoader,
)

app = FastAPI(title="NYC Taxi Demand Serving API")

# Load configuration and initialize Feature Store
_config_path = Path(__file__).resolve().parents[3] / "configs" / "project.yaml"
_config: ProjectConfig = ProjectConfigLoader().load(_config_path)
_store = FeatureStore(repo_path=str(_config.feast.repo_path))

# Set tracking URI and attempt to load champion model
mlflow.set_tracking_uri(_config.mlflow.tracking_uri)
_model_uri = f"models:/{_config.mlflow.registered_model_name}@champion"

try:
    _model = mlflow.pyfunc.load_model(_model_uri)
except Exception:
    _model = None


def fetch_online_features(location_id: int) -> pd.DataFrame:
    """Fetch recent demand features from Feast online SQLite store.

    Example:
        features = fetch_online_features(142)
    """
    entity_rows = [{"pickup_location_id": location_id}]
    feature_refs = [
        "hourly_pickup_demand:pickup_count",
        "hourly_pickup_demand:hour",
        "hourly_pickup_demand:day_of_week",
        "hourly_pickup_demand:is_weekend",
        "hourly_pickup_demand:month",
    ]
    features_df = _store.get_online_features(
        features=feature_refs,
        entity_rows=entity_rows,
    ).to_df()
    return features_df


@app.get("/predict/{location_id}")
def predict_demand(location_id: int) -> dict[str, Any]:
    """Retrieve online features and run prediction with the champion model.

    Example:
        GET /predict/142
    """
    if _model is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded. Ensure champion model is promoted in MLflow.",
        )

    try:
        features = fetch_online_features(location_id)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve features from Feature Store: {exc}",
        ) from exc

    if features.empty or pd.isna(features["pickup_count"].iloc[0]):
        raise HTTPException(
            status_code=404,
            detail=f"No online features found for location ID {location_id}",
        )

    feature_cols = [
        "pickup_count",
        "hour",
        "day_of_week",
        "is_weekend",
        "month",
    ]
    pred_features = features[feature_cols]

    prediction = _model.predict(pred_features)
    pred_val = float(prediction.iloc[0])

    return {
        "pickup_location_id": location_id,
        "features": features.to_dict(orient="records")[0],
        "predicted_demand": pred_val,
    }
