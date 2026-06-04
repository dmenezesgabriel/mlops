from importlib import import_module
from pathlib import Path


class LocalFeastMaterializer:
    """Run local Feast repository operations behind a project adapter.

    Example:
        LocalFeastMaterializer().apply(Path("feature_repo"))
    """

    def apply(self, feature_repo_path: Path) -> None:
        feature_store_type = import_module("feast").FeatureStore
        feature_store = feature_store_type(repo_path=str(feature_repo_path))
        feature_store.apply()
