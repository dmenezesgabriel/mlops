"""Named fakes for the feast/mlflow serving boundaries (ADR-0005)."""

from collections.abc import Callable
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd


class FakeRetrievalJob:
    """Feast retrieval-job stand-in carrying a fixed result frame."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def to_df(self) -> pd.DataFrame:
        return self._frame


class FakeFeatureStore:
    """Feast FeatureStore stand-in recording repo path and online reads."""

    instances: ClassVar[list["FakeFeatureStore"]] = []
    online_result: ClassVar[pd.DataFrame] = pd.DataFrame()
    online_error: ClassVar[Exception | None] = None

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.online_calls: list[tuple[list[str], list[dict[str, int]]]] = []
        type(self).instances.append(self)

    def get_online_features(
        self, features: list[str], entity_rows: list[dict[str, int]]
    ) -> FakeRetrievalJob:
        self.online_calls.append((features, entity_rows))
        if type(self).online_error is not None:
            raise type(self).online_error
        return FakeRetrievalJob(type(self).online_result)


class FakeFeastModule:
    """`feast` module stand-in for import-time seams."""

    FeatureStore = FakeFeatureStore


class FakePyfuncModel:
    """MLflow pyfunc model stand-in returning configured predictions."""

    def __init__(self, predictions: list[float] | None = None) -> None:
        self.predictions = predictions
        self.predicted_frames: list[pd.DataFrame] = []

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        self.predicted_frames.append(features)
        if self.predictions is None:
            return np.array([1.0] * len(features))
        return np.array(self.predictions)


class FakeMlflowPyfunc:
    """`mlflow.pyfunc` namespace stand-in with a scriptable load failure."""

    def __init__(self) -> None:
        self.model = FakePyfuncModel()
        self.load_error: Exception | None = None
        self.loaded_uris: list[str] = []

    def load_model(self, model_uri: str) -> FakePyfuncModel:
        self.loaded_uris.append(model_uri)
        if self.load_error is not None:
            raise self.load_error
        return self.model


class FakeMlflowModule:
    """`mlflow` module stand-in recording tracking calls without a server."""

    def __init__(self) -> None:
        self.tracking_uri: str | None = None
        self.pyfunc = FakeMlflowPyfunc()

    def set_tracking_uri(self, tracking_uri: str) -> None:
        self.tracking_uri = tracking_uri


class FakeMlflowClient:
    """`mlflow.client.MlflowClient` stand-in recording uri + alias calls."""

    instances: ClassVar[list["FakeMlflowClient"]] = []

    def __init__(self, tracking_uri: str | None = None) -> None:
        self.tracking_uri = tracking_uri
        self.alias_calls: list[dict[str, str]] = []
        type(self).instances.append(self)

    def set_registered_model_alias(
        self, name: str, alias: str, version: str
    ) -> None:
        self.alias_calls.append(
            {"name": name, "alias": alias, "version": version}
        )


class FakeMlflowClientModule:
    """`mlflow.client` module stand-in for the `import_module` seam."""

    MlflowClient = FakeMlflowClient


class FailingRunner:
    """Pipeline runner stand-in raising a scripted exception."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def __call__(self, config_path: Path) -> None:
        raise self._error


def import_module_for(mapping: dict[str, object]) -> Callable[[str], object]:
    """Build an `import_module` replacement dispatching to the mapping."""

    def _import(name: str) -> object:
        if name not in mapping:
            raise ImportError(
                f"Unexpected import {name}: expected one of {sorted(mapping)}"
            )
        return mapping[name]

    return _import


def reset_fake_state() -> None:
    """Reset ClassVar fake state between tests."""
    FakeFeatureStore.instances = []
    FakeFeatureStore.online_result = pd.DataFrame()
    FakeFeatureStore.online_error = None
    FakeMlflowClient.instances = []
