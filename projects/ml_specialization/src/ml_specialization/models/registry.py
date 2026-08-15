from importlib import import_module


class MlflowDemandModelRegistry:
    """Promote an MLflow registered model version to the champion alias.

    Example:
        MlflowDemandModelRegistry().promote_champion(model_name, version)
    """

    def promote_champion(self, model_name: str, version: str) -> None:
        mlflow = import_module("mlflow.client")
        client = mlflow.MlflowClient()
        client.set_registered_model_alias(
            name=model_name, alias="champion", version=version
        )
