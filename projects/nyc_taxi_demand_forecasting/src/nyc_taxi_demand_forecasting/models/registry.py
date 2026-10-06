"""MLflow model-registry lookups shared by the pipelines."""

from mlflow.client import MlflowClient


def latest_model_version(client: MlflowClient, model_name: str) -> str:
    """Resolve the highest registered version of `model_name`.

    `search_model_versions` returns an empty page for absent and
    versionless registrations alike — either way there is nothing to
    load (the deprecated `get_latest_versions` raised only for absent
    names and reported one row per stage, making `[0]` arbitrary).

    Example:
        latest_model_version(client, "nyc_taxi_demand_forecaster")
    """
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise ValueError(
            f"No registered model found with name {model_name}: "
            "expected at least one registered version"
        )
    return max(versions, key=lambda mv: int(mv.version)).version
