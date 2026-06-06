import sys
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

        # Dynamically append feature_repo to Python path to load definitions
        resolved_path = feature_repo_path.resolve()
        if str(resolved_path) not in sys.path:
            sys.path.insert(0, str(resolved_path))

        # Import local entities and feature views
        entities_module = import_module("entities")
        views_module = import_module("feature_views")

        pickup_location = entities_module.pickup_location
        hourly_pickup_demand_view = views_module.hourly_pickup_demand_view

        # Apply definitions programmatically to create/update registry
        feature_store.apply([pickup_location, hourly_pickup_demand_view])
