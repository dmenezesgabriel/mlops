from dataclasses import dataclass
from pathlib import Path

from mlops_shared.config import YamlMappingLoader
from mlops_shared.paths import RepositoryPathResolver


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    raw_data: Path
    interim_data: Path
    processed_data: Path
    models: Path
    reports: Path


@dataclass(frozen=True)
class CollectionConfig:
    year: int
    months: tuple[int, ...]
    taxi_type: str
    source_url_template: str

    def source_url(self, month: int) -> str:
        return self.source_url_template.format(
            year=self.year, month=month, taxi_type=self.taxi_type
        )


@dataclass(frozen=True)
class FeatureConfig:
    training_dataset_path: Path
    offline_features_path: Path


@dataclass(frozen=True)
class MlflowConfig:
    tracking_uri: str
    experiment_name: str
    registered_model_name: str


@dataclass(frozen=True)
class TrainingConfig:
    target_column: str
    test_size: float
    random_state: int


@dataclass(frozen=True)
class EvaluationConfig:
    max_mae: float
    max_rmse: float


@dataclass(frozen=True)
class FeastConfig:
    repo_path: Path


@dataclass(frozen=True)
class ProjectConfig:
    paths: ProjectPaths
    collection: CollectionConfig
    features: FeatureConfig
    mlflow: MlflowConfig
    training: TrainingConfig
    evaluation: EvaluationConfig
    feast: FeastConfig


class ProjectConfigLoader:
    """Load and validate project configuration from YAML.

    Example:
        ProjectConfigLoader().load(Path("configs/project.yaml"))
    """

    def __init__(self, yaml_loader: YamlMappingLoader | None = None) -> None:
        self._yaml_loader = yaml_loader or YamlMappingLoader()

    def load(self, config_path: Path) -> ProjectConfig:
        raw_config = self._yaml_loader.load(config_path)
        project_root = config_path.parent.parent.resolve()
        resolver = RepositoryPathResolver(project_root)
        return ProjectConfig(
            paths=self._paths(raw_config, project_root, resolver),
            collection=self._collection(raw_config),
            features=self._features(raw_config, resolver),
            mlflow=self._mlflow(raw_config),
            training=self._training(raw_config),
            evaluation=self._evaluation(raw_config),
            feast=self._feast(raw_config, resolver),
        )

    def _paths(
        self, raw_config: dict[str, object], project_root: Path, resolver: RepositoryPathResolver
    ) -> ProjectPaths:
        paths = self._mapping(raw_config, "paths")
        return ProjectPaths(
            root=project_root,
            raw_data=resolver.resolve(self._string(paths, "raw_data")),
            interim_data=resolver.resolve(self._string(paths, "interim_data")),
            processed_data=resolver.resolve(self._string(paths, "processed_data")),
            models=resolver.resolve(self._string(paths, "models")),
            reports=resolver.resolve(self._string(paths, "reports")),
        )

    def _collection(self, raw_config: dict[str, object]) -> CollectionConfig:
        collection = self._mapping(raw_config, "collection")
        return CollectionConfig(
            year=self._integer(collection, "year"),
            months=tuple(self._integer_list(collection, "months")),
            taxi_type=self._string(collection, "taxi_type"),
            source_url_template=self._string(collection, "source_url_template"),
        )

    def _features(
        self, raw_config: dict[str, object], resolver: RepositoryPathResolver
    ) -> FeatureConfig:
        features = self._mapping(raw_config, "features")
        return FeatureConfig(
            training_dataset_path=resolver.resolve(self._string(features, "training_dataset_path")),
            offline_features_path=resolver.resolve(self._string(features, "offline_features_path")),
        )

    def _mlflow(self, raw_config: dict[str, object]) -> MlflowConfig:
        mlflow = self._mapping(raw_config, "mlflow")
        return MlflowConfig(
            tracking_uri=self._string(mlflow, "tracking_uri"),
            experiment_name=self._string(mlflow, "experiment_name"),
            registered_model_name=self._string(mlflow, "registered_model_name"),
        )

    def _training(self, raw_config: dict[str, object]) -> TrainingConfig:
        training = self._mapping(raw_config, "training")
        return TrainingConfig(
            target_column=self._string(training, "target_column"),
            test_size=self._float(training, "test_size"),
            random_state=self._integer(training, "random_state"),
        )

    def _evaluation(self, raw_config: dict[str, object]) -> EvaluationConfig:
        evaluation = self._mapping(raw_config, "evaluation")
        return EvaluationConfig(
            max_mae=self._float(evaluation, "max_mae"),
            max_rmse=self._float(evaluation, "max_rmse"),
        )

    def _feast(
        self, raw_config: dict[str, object], resolver: RepositoryPathResolver
    ) -> FeastConfig:
        feast = self._mapping(raw_config, "feast")
        return FeastConfig(repo_path=resolver.resolve(self._string(feast, "repo_path")))

    def _mapping(self, config: dict[str, object], key: str) -> dict[str, object]:
        value = config.get(key)
        if isinstance(value, dict):
            return {str(item_key): item_value for item_key, item_value in value.items()}

        raise ValueError(f"Invalid project config key {key}: expected mapping")

    def _string(self, config: dict[str, object], key: str) -> str:
        value = config.get(key)
        if isinstance(value, str):
            return value

        raise ValueError(f"Invalid project config key {key}: expected string, got {value!r}")

    def _integer(self, config: dict[str, object], key: str) -> int:
        value = config.get(key)
        if isinstance(value, int):
            return value

        raise ValueError(f"Invalid project config key {key}: expected integer, got {value!r}")

    def _float(self, config: dict[str, object], key: str) -> float:
        value = config.get(key)
        if isinstance(value, int | float):
            return float(value)

        raise ValueError(f"Invalid project config key {key}: expected number, got {value!r}")

    def _integer_list(self, config: dict[str, object], key: str) -> list[int]:
        value = config.get(key)
        if isinstance(value, list) and all(isinstance(item, int) for item in value):
            return value

        raise ValueError(f"Invalid project config key {key}: expected integer list, got {value!r}")
