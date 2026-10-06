import sys
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path

import pytest
from fakes import (
    FakeFeastModule,
    FakeFeatureStore,
    import_module_for,
)
from nyc_taxi_demand_forecasting.features import feast_materialization
from nyc_taxi_demand_forecasting.features.feast_materialization import (
    LocalFeastMaterializer,
)

_REPO_MODULE_NAMES = ("data_sources", "entities", "feature_views")


def _write_feature_repo(repo_dir: Path, marker: str) -> None:
    """A minimal feature repo whose definitions are marker-valued sentinels.

    `feature_views` reaches `entities`/`data_sources` through plain sibling
    imports — the same shape as the real repo — so the marker on the applied
    view proves which repo's modules were bound during the load.
    """
    repo_dir.mkdir(parents=True)
    (repo_dir / "data_sources.py").write_text(
        f'hourly_demand_source = "{marker}_source"\n'
    )
    (repo_dir / "entities.py").write_text(
        f'pickup_location = "{marker}_entity"\n'
    )
    (repo_dir / "feature_views.py").write_text(
        "from data_sources import hourly_demand_source\n"
        "from entities import pickup_location\n"
        "hourly_pickup_demand_view = (\n"
        f'    "{marker}_view:" + pickup_location + "|" + hourly_demand_source\n'
        ")\n"
    )


def _patch_feast_import(
    monkeypatch: pytest.MonkeyPatch, real_fallback: bool = False
) -> None:
    fallback = import_module if real_fallback else None
    monkeypatch.setattr(
        feast_materialization,
        "import_module",
        import_module_for({"feast": FakeFeastModule}, fallback=fallback),
    )


@pytest.fixture
def _repo_import_state() -> Iterator[None]:
    """Restore sys.path/sys.modules after a test even on a failing path."""
    path_before = list(sys.path)
    modules_before = sys.modules.copy()
    yield
    sys.path[:] = path_before
    for name in _REPO_MODULE_NAMES:
        if name in modules_before:
            sys.modules[name] = modules_before[name]
        else:
            sys.modules.pop(name, None)


def test_apply_registers_entities_and_feature_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    repo_path = tmp_path / "feature_repo"
    _write_feature_repo(repo_path, "A")
    # No real-import fallback: repo modules must not route through
    # `import_module` at all — an unexpected name raises.
    _patch_feast_import(monkeypatch)

    # Act
    LocalFeastMaterializer().apply(repo_path)

    # Assert
    store = FakeFeatureStore.instances[0]
    assert store.repo_path == str(repo_path)
    assert store.applied_objects == [
        "A_entity",
        "A_view:A_entity|A_source",
    ]


def test_apply_second_repo_does_not_reuse_first_repo_modules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _repo_import_state: object,
) -> None:
    # Arrange — a second apply in one process must not see the first repo's
    # cached modules (the stale-sys.modules defect). The fallback exposes the
    # real import machinery so the defect is observable pre-fix.
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _write_feature_repo(repo_a, "A")
    _write_feature_repo(repo_b, "B")
    _patch_feast_import(monkeypatch, real_fallback=True)

    # Act
    LocalFeastMaterializer().apply(repo_a)
    LocalFeastMaterializer().apply(repo_b)

    # Assert
    first_store, second_store = FakeFeatureStore.instances
    assert first_store.applied_objects == [
        "A_entity",
        "A_view:A_entity|A_source",
    ]
    assert second_store.applied_objects == [
        "B_entity",
        "B_view:B_entity|B_source",
    ]


def test_apply_leaves_sys_path_and_sys_modules_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _repo_import_state: object,
) -> None:
    # Arrange — a pre-existing "entities" binding must survive the apply.
    preexisting = sys.modules["entities"] = object()
    path_before = list(sys.path)
    repo_path = tmp_path / "feature_repo"
    _write_feature_repo(repo_path, "A")
    _patch_feast_import(monkeypatch)

    # Act
    LocalFeastMaterializer().apply(repo_path)

    # Assert
    assert sys.path == path_before
    assert sys.modules["entities"] is preexisting
    assert "data_sources" not in sys.modules
    assert "feature_views" not in sys.modules


def test_apply_rejects_missing_repo_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — a repo missing its entities.py fails naming the file.
    repo_path = tmp_path / "feature_repo"
    repo_path.mkdir(parents=True)
    (repo_path / "data_sources.py").write_text('hourly_demand_source = "x"\n')
    (repo_path / "feature_views.py").write_text(
        'hourly_pickup_demand_view = "x"\n'
    )
    _patch_feast_import(monkeypatch)

    # Act / Assert
    with pytest.raises(FileNotFoundError, match="entities.py"):
        LocalFeastMaterializer().apply(repo_path)


def test_import_module_for_rejects_unmapped_names() -> None:
    # Arrange
    importer = import_module_for({})

    # Act / Assert
    with pytest.raises(ImportError, match="Unexpected import"):
        importer("socket")


def test_import_module_for_delegates_unmapped_names() -> None:
    # Arrange
    importer = import_module_for({}, fallback=lambda name: f"real:{name}")

    # Act / Assert
    assert importer("socket") == "real:socket"
