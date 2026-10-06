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

# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# This module runs inside the SageMaker training image: joblib/sklearn/
# catboost/xgboost/lightgbm are installed in the image, not the workspace
# (see [tool.deptry] DEP001 ignores), so their members are untyped here.

from __future__ import annotations

import json
import os

from joblib import dump
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.datasets import fetch_california_housing, load_iris

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

# dataset -> (task, loader). loaders return (X, y).
_DATASETS = {
    "california_housing": (
        "regression",
        lambda: fetch_california_housing(return_X_y=True),
    ),
    "iris": (
        "classification",
        lambda: (load_iris().data, load_iris().target),
    ),
}


def build_model(task: str) -> LGBMRegressor | LGBMClassifier:
    if task == "regression":
        return LGBMRegressor(n_estimators=50, verbose=-1)
    if task == "classification":
        return LGBMClassifier(
            n_estimators=50, objective="multiclass", verbose=-1
        )
    raise ValueError(f"unknown task: {task!r}")


def _parse_sm_hps() -> dict[str, object]:
    raw = os.environ.get("SM_HPS", "{}")
    try:
        hps = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"SM_HPS is not valid JSON: {exc}") from exc
    if not isinstance(hps, dict):
        raise ValueError(
            f"SM_HPS must be a JSON object, got {hps!r} ({type(hps).__name__})"
        )
    return hps


def main() -> None:
    dataset = _parse_sm_hps().get("dataset", "california_housing")
    if not isinstance(dataset, str) or dataset not in _DATASETS:
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
