from pathlib import Path

import pandas as pd
import pytest
from fakes import (
    FakeMlflowModule,
    FakePyfuncModel,
    import_module_for,
    training_frame,
)
from nyc_taxi_demand_forecasting.inference import (
    batch_predict as batch_predict_module,
)
from nyc_taxi_demand_forecasting.inference.batch_predict import (
    BatchDemandPredictor,
)


def test_batch_predictor_scores_rows_and_writes_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    input_path = tmp_path / "input.parquet"
    training_frame().to_parquet(input_path, index=False)
    fake_mlflow = FakeMlflowModule()
    fake_mlflow.pyfunc.model = FakePyfuncModel([1.5] * 10)
    monkeypatch.setattr(
        batch_predict_module,
        "import_module",
        import_module_for({"mlflow": fake_mlflow}),
    )

    # Act
    output_path = BatchDemandPredictor().predict(
        "models:/model/1",
        input_path,
        tmp_path / "scored" / "predictions.parquet",
    )

    # Assert
    written = pd.read_parquet(output_path)
    assert written["prediction"].to_list() == [1.5] * 10
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model/1"]
