import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from feast import FeatureStore
from mlflow.exceptions import MlflowException
from mlflow.pyfunc import PyFuncModel

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader

logger = logging.getLogger(__name__)

app = FastAPI(title="NYC Taxi Demand Serving API")

# api.py sits at src/nyc_taxi_demand_forecasting/inference/api.py — the
# project config lives at <project root>/configs/project.yaml, three parents up.
_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "project.yaml"
_FEATURE_COLUMNS = [
    "pickup_count",
    "hour",
    "day_of_week",
    "is_weekend",
    "month",
]


@dataclass(frozen=True)
class _ServingResources:
    store: FeatureStore
    model: PyFuncModel | None


_resources: _ServingResources | None = None


def _load_serving_resources() -> _ServingResources:
    """Build the store and champion model; a registry-level load failure logs
    the cause and degrades to the 503 contract — anything else propagates."""
    config = ProjectConfigLoader().load(_CONFIG_PATH)
    store = FeatureStore(repo_path=str(config.feast.repo_path))
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    model_uri = f"models:/{config.mlflow.registered_model_name}@champion"
    try:
        model: PyFuncModel | None = mlflow.pyfunc.load_model(model_uri)
    except MlflowException:
        logger.exception(
            "champion_model_load_failed", extra={"model_uri": model_uri}
        )
        model = None
    return _ServingResources(store=store, model=model)


def _serving_resources() -> _ServingResources:
    """Build serving resources on first request so importing this module
    stays side-effect free; a cached ``model=None`` keeps a missing champion
    a fast 503 instead of a per-request retry."""
    global _resources
    if _resources is None:
        _resources = _load_serving_resources()
    return _resources


def fetch_online_features(location_id: int) -> pd.DataFrame:
    """Fetch recent demand features from Feast online SQLite store.

    Example:
        features = fetch_online_features(142)
    """
    entity_rows = [{"pickup_location_id": location_id}]
    feature_refs = [
        f"hourly_pickup_demand:{name}" for name in _FEATURE_COLUMNS
    ]
    features_df = (
        _serving_resources()
        .store.get_online_features(
            features=feature_refs,
            entity_rows=entity_rows,
        )
        .to_df()
    )
    return features_df


def _features_missing(features: pd.DataFrame) -> bool:
    if features.empty or not set(_FEATURE_COLUMNS) <= set(features.columns):
        return True
    count_na: bool = features["pickup_count"].isna().iloc[0]
    return count_na


@app.get("/predict/{location_id}")
def predict_demand(location_id: int) -> dict[str, Any]:
    """Retrieve online features and run prediction with the champion model.

    Example:
        GET /predict/142
    """
    model = _serving_resources().model
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded. Ensure champion model is promoted in MLflow.",
        )

    try:
        features = fetch_online_features(location_id)
    except Exception as exc:
        logger.exception(
            "online_feature_fetch_failed",
            extra={"pickup_location_id": location_id},
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve features from the feature store",
        ) from exc

    if _features_missing(features):
        raise HTTPException(
            status_code=404,
            detail=f"No online features found for location ID {location_id}",
        )

    pred_features = features[_FEATURE_COLUMNS]

    raw_prediction: Any = model.predict(  # pyright: ignore[reportUnknownMemberType]
        pred_features
    )
    pred_val = float(np.asarray(raw_prediction).ravel()[0])

    return {
        "pickup_location_id": location_id,
        "features": features.to_dict(orient="records")[0],
        "predicted_demand": pred_val,
    }
