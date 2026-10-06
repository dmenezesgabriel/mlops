import sys
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

_REPO_DEFINITION_MODULES = ("data_sources", "entities", "feature_views")


class LocalFeastMaterializer:
    """Run local Feast repository operations behind a project adapter.

    Example:
        LocalFeastMaterializer().apply(Path("feature_repo"))
    """

    def apply(self, feature_repo_path: Path) -> None:
        feature_store_type = import_module("feast").FeatureStore
        feature_store = feature_store_type(repo_path=str(feature_repo_path))

        # Load the repo's definition modules by explicit file path — a second
        # apply on a different repo can never pick up stale sys.modules
        # entries, and sys.path stays untouched.
        modules = _load_repo_modules(feature_repo_path.resolve())
        feature_store.apply(
            [
                modules["entities"].pickup_location,
                modules["feature_views"].hourly_pickup_demand_view,
            ]
        )


def _load_repo_modules(repo_path: Path) -> dict[str, ModuleType]:
    """Load the repo's definition modules in dependency order.

    Sibling imports inside the repo (`from entities import …` in
    `feature_views.py`) resolve through `sys.modules`, so each freshly
    loaded module is bound under its real name only for the duration of the
    load; the caller's prior bindings are restored afterwards.
    """
    loaded: dict[str, ModuleType] = {}
    previous: dict[str, ModuleType | None] = {}
    try:
        for name in _REPO_DEFINITION_MODULES:
            loaded[name] = _exec_repo_module(repo_path, name, previous)
    finally:
        _restore_sys_modules(previous)
    return loaded


def _exec_repo_module(
    repo_path: Path, name: str, previous: dict[str, ModuleType | None]
) -> ModuleType:
    spec = spec_from_file_location(name, repo_path / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ValueError(
            f"Cannot load feature repo module {name!r}: expected a Python "
            f"file at {repo_path / f'{name}.py'}"
        )
    module = module_from_spec(spec)
    previous[name] = sys.modules.get(name)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _restore_sys_modules(previous: dict[str, ModuleType | None]) -> None:
    for name, prior in previous.items():
        if prior is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prior
