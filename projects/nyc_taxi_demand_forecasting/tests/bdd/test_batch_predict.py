"""Step definitions for the batch-predict BDD feature.

Steps drive `BatchDemandPredictor.predict` over real parquet files with
the `mlflow` seam faked through the existing `import_module` boundary —
the assembled load→project→score→write loop the class's unit pins cover
only as separate halves.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest
from fakes import FakeMlflowModule, import_module_for
from nyc_taxi_demand_forecasting.features.hourly_demand import (
    FEATURE_COLUMNS,
)
from nyc_taxi_demand_forecasting.inference import (
    batch_predict as batch_predict_module,
)
from nyc_taxi_demand_forecasting.inference.batch_predict import (
    BatchDemandPredictor,
)
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/batch_predict.feature")


@dataclass
class BatchRun:
    """State shared between the given/when/then steps of a scenario."""

    input_path: Path
    output_path: Path
    fake_mlflow: FakeMlflowModule = field(default_factory=FakeMlflowModule)


@pytest.fixture
def run(tmp_path: Path) -> BatchRun:
    return BatchRun(
        input_path=tmp_path / "input.parquet",
        output_path=tmp_path / "scored" / "output.parquet",
    )


@given("a parquet of processed demand rows")
def _input_parquet(run: BatchRun) -> None:
    # Arrange — an extra column rides along to prove the projection.
    pd.DataFrame(
        [
            {
                "pickup_count": 10,
                "hour": 8,
                "day_of_week": 1,
                "is_weekend": False,
                "month": 1,
                "extra_column": "ignored",
            },
            {
                "pickup_count": 4,
                "hour": 20,
                "day_of_week": 5,
                "is_weekend": True,
                "month": 1,
                "extra_column": "ignored",
            },
        ]
    ).to_parquet(run.input_path, index=False)


@given("the served model returns the predictions 12.5 and 8.0")
def _served_model(run: BatchRun) -> None:
    # Arrange
    run.fake_mlflow.pyfunc.model.predictions = [12.5, 8.0]


@when(parsers.parse('batch predict runs for "{model_uri}"'))
def _batch_predict(
    run: BatchRun, model_uri: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Act
    monkeypatch.setattr(
        batch_predict_module,
        "import_module",
        import_module_for({"mlflow": run.fake_mlflow}),
    )
    BatchDemandPredictor().predict(model_uri, run.input_path, run.output_path)


@then("the output parquet carries the predictions 12.5 and 8.0")
def _output_predictions(run: BatchRun) -> None:
    # Assert
    scored = pd.read_parquet(run.output_path)
    assert list(scored["prediction"]) == [12.5, 8.0]
    assert "extra_column" in scored.columns


@then("the model saw only the feature columns")
def _model_saw_features(run: BatchRun) -> None:
    # Assert — the serving contract is the FEATURE_COLUMNS projection.
    seen = run.fake_mlflow.pyfunc.model.predicted_frames[0]
    assert list(seen.columns) == list(FEATURE_COLUMNS)


@then(parsers.parse('the served model was loaded from "{model_uri}"'))
def _loaded_uri(run: BatchRun, model_uri: str) -> None:
    # Assert
    assert run.fake_mlflow.pyfunc.loaded_uris == [model_uri]
