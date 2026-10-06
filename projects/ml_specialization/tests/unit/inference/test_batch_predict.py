from pathlib import Path

import pandas as pd
import pytest
from fakes import FakeMlflowModule, import_module_for
from ml_specialization.inference import batch_predict as batch_predict_module
from ml_specialization.inference.batch_predict import BatchDemandPredictor


def _input_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "pickup_count": 10,
                "hour": 8,
                "day_of_week": 1,
                "is_weekend": False,
                "month": 1,
                "extra_column": "ignored",
            }
        ]
    )


def test_predict_writes_scored_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(
        batch_predict_module,
        "import_module",
        import_module_for({"mlflow": fake_mlflow}),
    )
    input_path = tmp_path / "input.parquet"
    _input_frame().to_parquet(input_path, index=False)
    output_path = tmp_path / "nested" / "output.parquet"

    # Act
    result = BatchDemandPredictor().predict(
        "models:/model/1", input_path, output_path
    )

    # Assert — the scored frame lands at the requested path.
    assert result == output_path
    assert fake_mlflow.pyfunc.loaded_uris == ["models:/model/1"]
    scored = pd.read_parquet(output_path)
    assert list(scored["prediction"]) == [1.0]
    assert "extra_column" in scored.columns


def test_predict_propagates_missing_feature_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — a frame lacking the feature columns fails loudly, not
    # silently scored.
    fake_mlflow = FakeMlflowModule()
    monkeypatch.setattr(
        batch_predict_module,
        "import_module",
        import_module_for({"mlflow": fake_mlflow}),
    )
    input_path = tmp_path / "input.parquet"
    pd.DataFrame([{"hour": 8}]).to_parquet(input_path, index=False)

    # Act / Assert
    with pytest.raises(KeyError):
        BatchDemandPredictor().predict(
            "models:/model/1", input_path, tmp_path / "output.parquet"
        )
