import sys
from pathlib import Path

import pytest
from fakes import (
    FakeFeastModule,
    FakeFeatureRepoEntitiesModule,
    FakeFeatureRepoViewsModule,
    FakeFeatureStore,
    import_module_for,
)
from nyc_taxi_demand_forecasting.features import feast_materialization
from nyc_taxi_demand_forecasting.features.feast_materialization import (
    LocalFeastMaterializer,
)


def _patch_import_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        feast_materialization,
        "import_module",
        import_module_for(
            {
                "feast": FakeFeastModule,
                "entities": FakeFeatureRepoEntitiesModule,
                "feature_views": FakeFeatureRepoViewsModule,
            }
        ),
    )


def test_apply_registers_entities_and_feature_views(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    repo_path = tmp_path / "feature_repo"
    _patch_import_module(monkeypatch)

    # Act
    LocalFeastMaterializer().apply(repo_path)

    # Assert
    store = FakeFeatureStore.instances[0]
    assert store.repo_path == str(repo_path)
    assert store.applied_objects == [
        FakeFeatureRepoEntitiesModule.pickup_location,
        FakeFeatureRepoViewsModule.hourly_pickup_demand_view,
    ]
    try:
        assert str(repo_path.resolve()) in sys.path
    finally:
        sys.path.remove(str(repo_path.resolve()))


def test_apply_does_not_duplicate_sys_path_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    repo_path = tmp_path / "feature_repo"
    resolved = str(repo_path.resolve())
    sys.path.insert(0, resolved)
    _patch_import_module(monkeypatch)

    # Act
    LocalFeastMaterializer().apply(repo_path)

    # Assert
    try:
        assert sys.path.count(resolved) == 1
    finally:
        sys.path.remove(resolved)


def test_import_module_for_rejects_unmapped_names() -> None:
    # Arrange
    importer = import_module_for({})

    # Act / Assert
    with pytest.raises(ImportError, match="Unexpected import"):
        importer("socket")
