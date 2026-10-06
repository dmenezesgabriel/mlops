from importlib import import_module

from ml_specialization.configuration import MlflowConfig


class MlflowDemandModelRegistry:
    """Promote an MLflow registered model version to the champion alias.

    The tracking URI comes from the injected config — never the ambient
    process state, which would write a stray ``mlflow.db`` to the cwd.

    Example:
        MlflowDemandModelRegistry(config.mlflow).promote_champion(
            model_name, version
        )
    """

    def __init__(self, config: MlflowConfig) -> None:
        self._config = config

    def promote_champion(self, model_name: str, version: str) -> None:
        mlflow = import_module("mlflow.client")
        client = mlflow.MlflowClient(tracking_uri=self._config.tracking_uri)
        client.set_registered_model_alias(
            name=model_name, alias="champion", version=version
        )
