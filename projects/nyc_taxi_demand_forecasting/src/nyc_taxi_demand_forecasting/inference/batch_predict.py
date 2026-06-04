from importlib import import_module
from pathlib import Path

import pandas as pd


class BatchDemandPredictor:
    """Score processed demand rows with an MLflow model URI.

    Example:
        BatchDemandPredictor().predict("models:/name/latest", input_path, output_path)
    """

    _feature_columns = ("pickup_count", "hour", "day_of_week", "is_weekend", "month")

    def predict(self, model_uri: str, input_path: Path, output_path: Path) -> Path:
        mlflow = import_module("mlflow")
        model = mlflow.pyfunc.load_model(model_uri)
        input_frame = pd.read_parquet(input_path)
        predictions = model.predict(input_frame.loc[:, list(self._feature_columns)])
        output_frame = input_frame.assign(prediction=predictions)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_frame.to_parquet(output_path, index=False)
        return output_path
