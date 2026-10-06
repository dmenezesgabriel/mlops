from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeProjectConfigLoader,
    FakeTripPreprocessor,
    project_config,
)
from nyc_taxi_demand_forecasting.pipelines import preprocess


def test_preprocess_runs_trip_preprocessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    config = project_config(tmp_path)
    monkeypatch.setattr(
        preprocess,
        "ProjectConfigLoader",
        partial(FakeProjectConfigLoader, config),
    )
    monkeypatch.setattr(
        preprocess, "YellowTaxiTripPreprocessor", FakeTripPreprocessor
    )

    # Act
    preprocess.run(tmp_path / "configs" / "project.yaml")

    # Assert
    preprocessor = FakeTripPreprocessor.instances[0]
    assert preprocessor.preprocess_calls == [
        (
            config.paths.raw_data,
            config.paths.interim_data,
            config.collection,
        )
    ]
