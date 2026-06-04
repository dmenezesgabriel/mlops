from importlib import import_module

from nyc_taxi_demand_forecasting.configuration import MlflowConfig


class MlflowDemandModelRegistry:
    """Isolate MLflow model registry operations from project core code.

    Example:
        MlflowDemandModelRegistry(config).registered_model_name()
    """

    def __init__(self, config: MlflowConfig) -> None:
        self._config = config

    def registered_model_name(self) -> str:
        import_module("mlflow").set_tracking_uri(self._config.tracking_uri)
        return self._config.registered_model_name
