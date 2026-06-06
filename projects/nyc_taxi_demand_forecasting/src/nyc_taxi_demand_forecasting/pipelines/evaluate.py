import logging
from pathlib import Path

import mlflow
import pandas as pd
from mlflow.client import MlflowClient
from mlops_shared.evaluation import RegressionMetricCalculator

from nyc_taxi_demand_forecasting.configuration import ProjectConfigLoader
from nyc_taxi_demand_forecasting.models.training import DemandDatasetSplitter


def run(config_path: Path) -> None:
    config = ProjectConfigLoader().load(config_path)

    # 1. Load entities dataframe and fetch test historical features from Feast
    entity_df = pd.read_parquet(config.features.training_dataset_path)
    if "event_timestamp" not in entity_df.columns:
        entity_df["event_timestamp"] = pd.to_datetime(entity_df["pickup_hour"])
    entity_df["event_timestamp"] = pd.to_datetime(entity_df["event_timestamp"])
    entity_df = entity_df[
        ["pickup_location_id", "event_timestamp", "next_hour_pickup_count"]
    ]

    from feast import FeatureStore

    store = FeatureStore(repo_path=str(config.feast.repo_path))
    training_data = store.get_historical_features(
        entity_df=entity_df,
        features=[
            "hourly_pickup_demand:pickup_count",
            "hourly_pickup_demand:hour",
            "hourly_pickup_demand:day_of_week",
            "hourly_pickup_demand:is_weekend",
            "hourly_pickup_demand:month",
        ],
    ).to_df()

    # Split dataset (only evaluate on test split)
    _, test_frame = DemandDatasetSplitter().split(
        training_data, config.training.test_size
    )

    # 2. Connect to MLflow and get the latest registered model version
    mlflow.set_tracking_uri(config.mlflow.tracking_uri)
    client = MlflowClient()

    model_name = config.mlflow.registered_model_name
    latest_versions = client.get_latest_versions(name=model_name)
    if not latest_versions:
        raise ValueError(f"No registered model found with name {model_name}")

    latest_version = latest_versions[0].version
    model_uri = f"models:/{model_name}/{latest_version}"

    # 3. Load the model and make predictions
    model = mlflow.pyfunc.load_model(model_uri)
    feature_columns = [
        "pickup_count",
        "hour",
        "day_of_week",
        "is_weekend",
        "month",
    ]
    predictions = model.predict(test_frame.loc[:, feature_columns])

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

    # 5. Tag the candidate model version with its evaluation results
    client.set_model_version_tag(
        name=model_name,
        version=latest_version,
        key="evaluated",
        value="true",
    )
    client.set_model_version_tag(
        name=model_name,
        version=latest_version,
        key="mae",
        value=str(round(metrics.mae, 4)),
    )
    client.set_model_version_tag(
        name=model_name,
        version=latest_version,
        key="rmse",
        value=str(round(metrics.rmse, 4)),
    )

    # Validate against thresholds
    metrics.require_within(config.evaluation)
