from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeProjectConfigLoader,
    FakeTlcCollector,
    project_config,
)
from nyc_taxi_demand_forecasting.pipelines import collect


def test_collect_runs_tlc_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    monkeypatch.setattr(
        collect,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(
        collect, "TlcYellowTaxiParquetCollector", FakeTlcCollector
    )
    config_path = tmp_path / "configs" / "project.yaml"

    # Act
    collect.run(config_path)

    # Assert
    collector = FakeTlcCollector.instances[0]
    assert collector.collect_calls == [
        (config.collection, config.paths.raw_data)
    ]
    assert FakeProjectConfigLoader.instances[0].loaded_paths == [config_path]
