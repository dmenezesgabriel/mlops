"""Training entry point run by SageMaker local mode inside the job container.

The script is invoked via the ``train`` console script (sagemaker-training
5.1.1) with ``SM_HPS`` + ``SM_MODEL_DIR=/opt/ml/model`` set by the SDK. It loads
one of the supported sklearn built-in datasets named by the ``dataset``
hyperparameter and persists a joblib pipeline to ``SM_MODEL_DIR/model.joblib``.

Example:
    SAM = sagemaker.scikit_learn.SKLearn(
        entry_point="train.py",
        hyperparameters={"dataset": "california_housing"},
        ...
    )
"""

from __future__ import annotations

import json
import os

from joblib import dump
from sklearn.datasets import fetch_california_housing, load_breast_cancer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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
    "breast_cancer": (
        "classification",
        lambda: (load_breast_cancer().data, load_breast_cancer().target),
    ),
}


def build_model(task: str) -> Pipeline:
    if task == "regression":
        return Pipeline([("scale", StandardScaler()), ("model", Ridge())])
    if task == "classification":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000)),
            ]
        )
    raise ValueError(f"unknown task: {task!r}")


def main() -> None:
    hps = json.loads(os.environ.get("SM_HPS", "{}"))
    dataset = hps.get("dataset", "california_housing")
    if dataset not in _DATASETS:
        raise ValueError(
            f"unsupported dataset: {dataset!r}; expected one of "
            f"{sorted(_DATASETS)}"
        )
    task, loader = _DATASETS[dataset]
    x, y = loader()
    model = build_model(task).fit(x, y)
    os.makedirs(MODEL_DIR, exist_ok=True)
    dump(model, os.path.join(MODEL_DIR, "model.joblib"))


if __name__ == "__main__":
    main()
