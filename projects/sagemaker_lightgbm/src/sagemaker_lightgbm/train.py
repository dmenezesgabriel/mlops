"""Training entry point run by SageMaker local mode inside the job container.

Invoked via the ``train`` console script (sagemaker-training 5.1.1) with
``SM_HPS`` + ``SM_MODEL_DIR`` set by the SDK. Loads one of the supported
LightGBM built-in datasets named by the ``dataset`` hyperparameter and persists
a joblib model to ``SM_MODEL_DIR/model.joblib``.

Example:
    from sagemaker.estimator import Estimator
    Estimator(entry_point="train.py", image_uri="sagemaker-local:latest",
              hyperparameters={"dataset": "iris"})
"""

from __future__ import annotations

import json
import os

from joblib import dump
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.datasets import fetch_california_housing, load_iris

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

# dataset -> (task, loader). loaders return (X, y) from sklearn's Bunch.
_DATASETS = {
    "california_housing": (
        "regression",
        lambda: (
            fetch_california_housing().data,
            fetch_california_housing().target,
        ),
    ),
    "iris": (
        "classification",
        lambda: (load_iris().data, load_iris().target),
    ),
}


def build_model(task: str):
    if task == "regression":
        return LGBMRegressor(n_estimators=50, verbose=-1)
    if task == "classification":
        return LGBMClassifier(
            n_estimators=50, objective="multiclass", verbose=-1
        )
    raise ValueError(f"unknown task: {task!r}")


def main() -> None:
    hps = json.loads(os.environ.get("SM_HPS", "{}"))
    dataset = hps.get("dataset", "california_housing")
    if dataset not in _DATASETS:
        raise ValueError(
            f"unsupported dataset: {dataset!r}; expected one of {sorted(_DATASETS)}"
        )
    task, loader = _DATASETS[dataset]
    x, y = loader()
    model = build_model(task).fit(x, y)
    os.makedirs(MODEL_DIR, exist_ok=True)
    dump(model, os.path.join(MODEL_DIR, "model.joblib"))


if __name__ == "__main__":
    main()
