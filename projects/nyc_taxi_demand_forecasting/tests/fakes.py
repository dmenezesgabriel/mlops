"""Named fakes for the project's external I/O boundaries.

Pipelines and model classes reach Feast, MLflow, and requests through
module-level imports, so tests patch the name in the consuming module and
inject these fakes. Frame builders live here because the parquet round-trip
tests repeat the same arrange shape.
"""

from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd
from mlflow.exceptions import MlflowException
from nyc_taxi_demand_forecasting.configuration import (
    CollectionConfig,
    EvaluationConfig,
    FeastConfig,
    FeatureConfig,
    MlflowConfig,
    ProjectConfig,
    ProjectPaths,
    TrainingConfig,
)


class FakeRetrievalJob:
    """Feast retrieval-job stand-in carrying a fixed result frame."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def to_df(self) -> pd.DataFrame:
        return self._frame


class FakeFeatureStore:
    """Feast FeatureStore stand-in recording repo and store operations."""

    instances: ClassVar[list["FakeFeatureStore"]] = []
    historical_result: ClassVar[pd.DataFrame] = pd.DataFrame()
    online_result: ClassVar[pd.DataFrame] = pd.DataFrame()
    online_error: ClassVar[Exception | None] = None

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.historical_calls: list[tuple[pd.DataFrame, list[str]]] = []
        self.online_calls: list[tuple[list[str], list[dict[str, int]]]] = []
        self.applied_objects: list[object] = []
        self.materialized_windows: list[tuple[object, object]] = []
        type(self).instances.append(self)

    def get_historical_features(
        self, entity_df: pd.DataFrame, features: list[str]
    ) -> FakeRetrievalJob:
        self.historical_calls.append((entity_df, features))
        return FakeRetrievalJob(type(self).historical_result)

    def get_online_features(
        self, features: list[str], entity_rows: list[dict[str, int]]
    ) -> FakeRetrievalJob:
        if type(self).online_error is not None:
            raise type(self).online_error
        self.online_calls.append((features, entity_rows))
        return FakeRetrievalJob(type(self).online_result)

    def apply(self, objects: list[object]) -> None:
        self.applied_objects = list(objects)

    def materialize(self, start_date: object, end_date: object) -> None:
        self.materialized_windows.append((start_date, end_date))


class FakeFeastModule:
    """`feast` module stand-in for `import_module("feast")` seams."""

    FeatureStore = FakeFeatureStore


class FakeModelVersion:
    def __init__(self, version: str) -> None:
        self.version = version


class FakeMlflowExperiment:
    def __init__(self, experiment_id: str) -> None:
        self.experiment_id = experiment_id


class FakePyfuncModel:
    """MLflow pyfunc model stand-in returning configured predictions.

    `as_ndarray` returns the canonical ndarray the real pyfunc contract
    emits; the Series default stays until the remaining predict sites stop
    casting (their flip is a later fix item). `as_2d` returns a `(1, N)`
    row-matrix — the shape list-of-rows wrappers emit; it is 2-D rather
    than `(N, 1)` because pandas squeezes a column matrix on assignment.
    """

    def __init__(
        self,
        predictions: list[float] | None = None,
        as_ndarray: bool = False,
        as_2d: bool = False,
    ) -> None:
        self.predictions = predictions
        self.as_ndarray = as_ndarray
        self.as_2d = as_2d
        self.predicted_frames: list[pd.DataFrame] = []

    def predict(self, features: pd.DataFrame) -> pd.Series | np.ndarray:
        self.predicted_frames.append(features)
        values = (
            self.predictions
            if self.predictions is not None
            else [1.0] * len(features)
        )
        if self.as_2d:
            return np.array([values])
        if self.as_ndarray:
            return np.array(values)
        return pd.Series(values)


class FakeMlflowPyfunc:
    """`mlflow.pyfunc` namespace stand-in with per-URI load failures."""

    def __init__(self) -> None:
        self.model = FakePyfuncModel()
        self.load_errors: dict[str, Exception] = {}
        self.loaded_uris: list[str] = []
        self.logged_models: list[dict[str, object]] = []

    def load_model(self, model_uri: str) -> FakePyfuncModel:
        self.loaded_uris.append(model_uri)
        if model_uri in self.load_errors:
            raise self.load_errors[model_uri]
        return self.model

    def log_model(
        self,
        artifact_path: str,
        python_model: object,
        registered_model_name: str,
    ) -> None:
        self.logged_models.append(
            {
                "artifact_path": artifact_path,
                "python_model": python_model,
                "registered_model_name": registered_model_name,
            }
        )


class FakeMlflowModule:
    """`mlflow` module stand-in recording calls without a tracking server."""

    def __init__(self) -> None:
        self.tracking_uri: str | None = None
        self.experiment_name: str | None = None
        self.run_names: list[str | None] = []
        self.params: dict[str, object] = {}
        self.metrics: dict[str, object] = {}
        self.texts: dict[str, str] = {}
        self.experiment: FakeMlflowExperiment | None = None
        self.search_result: object = pd.DataFrame()
        self.pyfunc = FakeMlflowPyfunc()

    def set_tracking_uri(self, tracking_uri: str) -> None:
        self.tracking_uri = tracking_uri

    def set_experiment(self, experiment_name: str) -> None:
        self.experiment_name = experiment_name

    def start_run(
        self, run_name: str | None = None, nested: bool = False
    ) -> object:
        self.run_names.append(run_name)
        return nullcontext()

    def log_param(self, key: str, value: object) -> None:
        self.params[key] = value

    def log_metric(self, key: str, value: float) -> None:
        self.metrics[key] = value

    def log_metrics(self, metrics: dict[str, float]) -> None:
        self.metrics.update(metrics)

    def log_text(self, text: str, artifact_file: str) -> None:
        self.texts[artifact_file] = text

    def get_experiment_by_name(self, name: str) -> FakeMlflowExperiment | None:
        return self.experiment

    def search_runs(
        self,
        experiment_ids: object,
        filter_string: str,
        order_by: list[str],
        max_results: int,
    ) -> object:
        return self.search_result


class FakeMlflowClient:
    """`mlflow.client.MlflowClient` stand-in with a configurable registry."""

    instances: ClassVar[list["FakeMlflowClient"]] = []

    def __init__(
        self,
        versions: list[FakeModelVersion] | None = None,
        alias_versions: dict[tuple[str, str], FakeModelVersion] | None = None,
    ) -> None:
        self._versions = list(versions or [])
        self._alias_versions = dict(alias_versions or {})
        self.alias_calls: list[dict[str, object]] = []
        self.tag_calls: list[dict[str, object]] = []
        self.search_calls: list[str] = []
        type(self).instances.append(self)

    def search_model_versions(
        self, filter_string: str
    ) -> list[FakeModelVersion]:
        # Mirrors the real store contract: a missing or versionless model
        # name returns an empty page — it never raises.
        self.search_calls.append(filter_string)
        return list(self._versions)

    def get_model_version_by_alias(
        self, name: str, alias: str
    ) -> FakeModelVersion:
        key = (name, alias)
        if key not in self._alias_versions:
            raise MlflowException(
                f"Invalid alias lookup {key}: expected a registered alias"
            )
        return self._alias_versions[key]

    def set_registered_model_alias(
        self, name: str, alias: str, version: str
    ) -> None:
        self.alias_calls.append(
            {"name": name, "alias": alias, "version": version}
        )

    def set_model_version_tag(
        self, name: str, version: str, key: str, value: str
    ) -> None:
        self.tag_calls.append(
            {"name": name, "version": version, "key": key, "value": value}
        )


class FakeHttpResponse:
    def __init__(self, content: bytes, error: Exception | None) -> None:
        self.content = content
        self._error = error

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error


class FakeRequestsModule:
    """`requests` module stand-in for the parquet collector."""

    def __init__(
        self, content: bytes = b"parquet", error: Exception | None = None
    ) -> None:
        self.urls: list[str] = []
        self._content = content
        self._error = error

    def get(self, url: str, timeout: int) -> FakeHttpResponse:
        self.urls.append(url)
        return FakeHttpResponse(self._content, self._error)


class FakeRecordingBuilder:
    """Two-path builder stand-in for the dataset/feature builders."""

    instances: ClassVar[list["FakeRecordingBuilder"]] = []

    def __init__(self) -> None:
        self.build_calls: list[tuple[object, object]] = []
        type(self).instances.append(self)

    def build(self, input_path: object, output_path: object) -> None:
        self.build_calls.append((input_path, output_path))


class FakeFeastMaterializer:
    instances: ClassVar[list["FakeFeastMaterializer"]] = []

    def __init__(self) -> None:
        self.applied_repos: list[object] = []
        type(self).instances.append(self)

    def apply(self, feature_repo_path: object) -> None:
        self.applied_repos.append(feature_repo_path)


class FakeTlcCollector:
    instances: ClassVar[list["FakeTlcCollector"]] = []

    def __init__(self) -> None:
        self.collect_calls: list[tuple[object, object]] = []
        type(self).instances.append(self)

    def collect(self, config: object, output_directory: object) -> None:
        self.collect_calls.append((config, output_directory))


class FakeTripPreprocessor:
    instances: ClassVar[list["FakeTripPreprocessor"]] = []

    def __init__(self) -> None:
        self.preprocess_calls: list[tuple[object, object, object]] = []
        type(self).instances.append(self)

    def preprocess(
        self,
        raw_directory: object,
        output_directory: object,
        collection: object,
    ) -> None:
        self.preprocess_calls.append(
            (raw_directory, output_directory, collection)
        )


class FakeDemandModelTrainer:
    instances: ClassVar[list["FakeDemandModelTrainer"]] = []

    def __init__(self) -> None:
        self.train_calls: list[dict[str, object]] = []
        type(self).instances.append(self)

    def train(
        self,
        dataset_path: object,
        model_directory: object,
        training_config: object,
        mlflow_config: object,
        feast_config: object,
        alpha: float = 1.0,
    ) -> None:
        self.train_calls.append(
            {
                "dataset_path": dataset_path,
                "model_directory": model_directory,
                "training_config": training_config,
                "mlflow_config": mlflow_config,
                "feast_config": feast_config,
                "alpha": alpha,
            }
        )


class FakeDemandModelTuner:
    instances: ClassVar[list["FakeDemandModelTuner"]] = []
    result: ClassVar[object] = None

    def __init__(self) -> None:
        self.select_calls: list[tuple[object, ...]] = []
        type(self).instances.append(self)

    def select_best(self, *args: object) -> object:
        self.select_calls.append(args)
        return type(self).result


class FakeLoggingConfigurator:
    instances: ClassVar[list["FakeLoggingConfigurator"]] = []

    def __init__(self) -> None:
        self.configured = False
        type(self).instances.append(self)

    def configure(self) -> None:
        self.configured = True


class FakeProjectConfigLoader:
    """Loader stand-in returning one canned config; pair with partial()."""

    instances: ClassVar[list["FakeProjectConfigLoader"]] = []

    def __init__(self, config: ProjectConfig) -> None:
        self._config = config
        self.loaded_paths: list[Path] = []
        type(self).instances.append(self)

    def load(self, config_path: Path) -> ProjectConfig:
        self.loaded_paths.append(config_path)
        return self._config


class FailingRunner:
    """Pipeline runner stand-in raising a scripted exception."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def __call__(self, config_path: Path) -> None:
        raise self._error


class RecordingRunner:
    """Pipeline runner stand-in recording the config paths it ran with."""

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def __call__(self, config_path: Path) -> None:
        self.calls.append(config_path)


def import_module_for(
    mapping: dict[str, object],
    fallback: Callable[[str], object] | None = None,
) -> Callable[[str], object]:
    """Build an `import_module` replacement dispatching to the mapping.

    Unmapped names raise unless `fallback` is given — pass the real
    `import_module` when the test needs genuine import machinery for names
    outside the faked set (e.g. feature-repo definition modules).
    """

    def _import(name: str) -> object:
        if name in mapping:
            return mapping[name]
        if fallback is not None:
            return fallback(name)
        raise ImportError(
            f"Unexpected import {name}: expected one of {sorted(mapping)}"
        )

    return _import


def project_config(root: Path) -> ProjectConfig:
    """A valid ProjectConfig rooted entirely under `root` (tmp_path)."""
    data_dir = root / "data"
    return ProjectConfig(
        paths=ProjectPaths(
            root=root,
            raw_data=data_dir / "raw",
            interim_data=data_dir / "interim",
            processed_data=data_dir / "processed",
            models=root / "models",
            reports=root / "reports",
        ),
        collection=CollectionConfig(
            year=2023,
            months=(1, 3),
            taxi_type="yellow",
            source_url_template=(
                "https://example.test/{taxi_type}_{year}-{month:02d}.parquet"
            ),
        ),
        features=FeatureConfig(
            training_dataset_path=data_dir
            / "processed"
            / "training_dataset.parquet",
            offline_features_path=data_dir
            / "processed"
            / "hourly_demand_features.parquet",
        ),
        mlflow=MlflowConfig(
            tracking_uri=f"sqlite:///{root}/mlflow.db",
            experiment_name="test_experiment",
            registered_model_name="model",
        ),
        training=TrainingConfig(
            target_column="next_hour_pickup_count",
            test_size=0.2,
            random_state=42,
        ),
        evaluation=EvaluationConfig(max_mae=100.0, max_rmse=100.0),
        feast=FeastConfig(repo_path=root / "feature_repo"),
    )


def trips_frame() -> pd.DataFrame:
    """Raw trip columns matching `YellowTaxiTripPreprocessor._columns`."""
    return pd.DataFrame(
        {
            "tpep_pickup_datetime": pd.to_datetime(
                ["2023-01-01 00:05:00", "2023-01-01 01:10:00"]
            ),
            "tpep_dropoff_datetime": pd.to_datetime(
                ["2023-01-01 00:20:00", "2023-01-01 01:40:00"]
            ),
            "PULocationID": [1, 1],
            "DOLocationID": [2, 3],
            "passenger_count": [1, 2],
            "trip_distance": [1.5, 2.5],
            "fare_amount": [8.0, 12.0],
        }
    )


def entity_frame() -> pd.DataFrame:
    """Entity rows for Feast historical-feature lookups."""
    return pd.DataFrame(
        {
            "pickup_location_id": [1] * 10,
            "pickup_hour": pd.to_datetime(
                [f"2023-01-01 {hour:02d}:00:00" for hour in range(10)]
            ),
            "next_hour_pickup_count": list(range(10)),
        }
    )


def training_frame() -> pd.DataFrame:
    """Training dataset columns the trainer/tuner/monitor consume."""
    return pd.DataFrame(
        {
            "pickup_location_id": [1] * 10,
            "pickup_hour": pd.to_datetime(
                [f"2023-01-01 {hour:02d}:00:00" for hour in range(10)]
            ),
            "pickup_count": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
            "hour": list(range(10)),
            "day_of_week": [6] * 10,
            "is_weekend": [True] * 10,
            "month": [1] * 10,
            "next_hour_pickup_count": [11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
        }
    )


_INSTANCE_HOLDERS = (
    FakeFeatureStore,
    FakeMlflowClient,
    FakeRecordingBuilder,
    FakeFeastMaterializer,
    FakeTlcCollector,
    FakeTripPreprocessor,
    FakeDemandModelTrainer,
    FakeDemandModelTuner,
    FakeLoggingConfigurator,
    FakeProjectConfigLoader,
)


def reset_fake_state() -> None:
    """Clear per-test fake registries; the autouse fixture calls this."""
    for holder_type in _INSTANCE_HOLDERS:
        holder_type.instances.clear()
    FakeFeatureStore.historical_result = pd.DataFrame()
    FakeFeatureStore.online_result = pd.DataFrame()
    FakeFeatureStore.online_error = None
    FakeDemandModelTuner.result = None
