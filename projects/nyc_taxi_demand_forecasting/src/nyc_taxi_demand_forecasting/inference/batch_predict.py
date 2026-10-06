from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nyc_taxi_demand_forecasting.features.hourly_demand import FEATURE_COLUMNS


class BatchDemandPredictor:
    """Score processed demand rows with an MLflow model URI.

    Example:
        BatchDemandPredictor().predict("models:/name/latest", input_path, output_path)
    """

    def predict(
        self, model_uri: str, input_path: Path, output_path: Path
    ) -> Path:
        mlflow = import_module("mlflow")
        model = mlflow.pyfunc.load_model(model_uri)
        input_frame = pd.read_parquet(input_path)
        # pyfunc emits an ndarray, so normalize the output shape before the
        # frame assignment instead of trusting a Series.
        raw_predictions: Any = model.predict(
            input_frame.loc[:, list(FEATURE_COLUMNS)]
        )
        predictions = np.asarray(raw_predictions).ravel()
        output_frame = input_frame.assign(prediction=predictions)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_frame.to_parquet(output_path, index=False)
        return output_path
