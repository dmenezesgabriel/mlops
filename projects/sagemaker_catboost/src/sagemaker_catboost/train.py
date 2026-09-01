"""Training entry point run by SageMaker local mode inside the job container.

Invoked via the ``train`` console script (sagemaker-training 5.1.1) with
``SM_HPS`` + ``SM_MODEL_DIR`` set by the SDK. Loads one of the supported CatBoost
built-in datasets named by the ``dataset`` hyperparameter and persists a joblib
model to ``SM_MODEL_DIR/model.joblib``.

Example:
    from sagemaker.estimator import Estimator
    Estimator(entry_point="train.py", image_uri="sagemaker-local:latest",
              hyperparameters={"dataset": "breast_cancer"})
"""

from __future__ import annotations

import json
import os
import tempfile

from catboost import CatBoostClassifier, CatBoostRegressor
from joblib import dump
from sklearn.datasets import load_breast_cancer, load_diabetes

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
# CatBoost writes its per-run training log dir to cwd by default; route it to
# a temp dir so it never pollutes the mounted /opt/ml/code source tree.
CATBOOST_TRAIN_DIR = os.path.join(tempfile.gettempdir(), "catboost-info")

# dataset -> (task, loader). loaders return (X, y) from sklearn's Bunch.
_DATASETS = {
    "diabetes": (
        "regression",
        lambda: (load_diabetes().data, load_diabetes().target),
    ),
    "breast_cancer": (
        "classification",
        lambda: (load_breast_cancer().data, load_breast_cancer().target),
    ),
}


def build_model(task: str):
    if task == "regression":
        return CatBoostRegressor(
            iterations=50, verbose=0, train_dir=CATBOOST_TRAIN_DIR
        )
    if task == "classification":
        return CatBoostClassifier(
            iterations=50, verbose=0, train_dir=CATBOOST_TRAIN_DIR
        )
    raise ValueError(f"unknown task: {task!r}")


def main() -> None:
    hps = json.loads(os.environ.get("SM_HPS", "{}"))
    dataset = hps.get("dataset", "diabetes")
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
