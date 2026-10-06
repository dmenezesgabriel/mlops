import logging
from importlib import import_module
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
from mlflow.client import MlflowClient
from mlops_shared.evaluation import (
    RegressionMetricCalculator,
    RegressionMetrics,
)

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.features.hourly_demand import (
    FEATURE_COLUMNS,
    FEATURE_REFS,
    load_entity_df,
)
from nyc_taxi_demand_forecasting.models.registry import latest_model_version
from nyc_taxi_demand_forecasting.models.training import DemandDatasetSplitter


def _tag_evaluation_outcome(
    client: MlflowClient,
    model_name: str,
    model_version: str,
    outcome: str,
    metrics: RegressionMetrics,
) -> None:
    for key, value in (
        ("evaluated", outcome),
        ("mae", str(round(metrics.mae, 4))),
        ("rmse", str(round(metrics.rmse, 4))),
    ):
        client.set_model_version_tag(
            name=model_name,
            version=model_version,
            key=key,
            value=value,
        )


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # 1. Load entities dataframe and fetch test historical features from Feast
    entity_df = load_entity_df(config.features.training_dataset_path)

    feature_store_type = import_module("feast").FeatureStore
    store = feature_store_type(repo_path=str(config.feast.repo_path))
    training_data = store.get_historical_features(
        entity_df=entity_df,
        features=list(FEATURE_REFS),
    ).to_df()

    # Split dataset (only evaluate on test split)
    _, test_frame = DemandDatasetSplitter().split(
        training_data, config.training.test_size
    )

    # 2. Connect to MLflow and get the latest registered model version
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    client = MlflowClient()

    model_name = config.mlflow.registered_model_name
    latest_version = latest_model_version(client, model_name)
    model_uri = f"models:/{model_name}/{latest_version}"

    # 3. Load the model and make predictions
    model = mlflow.pyfunc.load_model(model_uri)
    # pyfunc emits an ndarray, so normalize the output shape instead of
    # asserting a Series — same contract the api/monitor sites carry.
    raw_predictions: Any = model.predict(  # pyright: ignore[reportUnknownMemberType]
        test_frame.loc[:, list(FEATURE_COLUMNS)]
    )
    predictions = np.asarray(raw_predictions).ravel()

    # 4. Compute metrics
    metrics = RegressionMetricCalculator().calculate(
        test_frame[config.training.target_column], predictions
    )

    logging.getLogger(__name__).info(
        "model_evaluation_completed",
        extra={
            "mae": metrics.mae,
            "rmse": metrics.rmse,
            "r2": metrics.r2,
            "version": latest_version,
        },
    )

    # 5. Gate before tagging — only a pass marks the version deployable via
    # the candidate alias; a failure records its truthful outcome so a
    # gate-failed version is distinguishable from a never-evaluated one.
    try:
        metrics.require_within(config.evaluation)
    except ValueError:
        _tag_evaluation_outcome(
            client, model_name, latest_version, "failed", metrics
        )
        raise
    _tag_evaluation_outcome(
        client, model_name, latest_version, "true", metrics
    )
    client.set_registered_model_alias(
        name=model_name,
        alias="candidate",
        version=latest_version,
    )
