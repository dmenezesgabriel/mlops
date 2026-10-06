"""Training entry point run by SageMaker local mode inside the job container.

Invoked via the ``train`` console script (sagemaker-training 5.1.1) with
``SM_HPS`` + ``SM_MODEL_DIR`` set by the SDK. Loads one of the supported XGBoost
built-in datasets named by the ``dataset`` hyperparameter and persists a
joblib model to ``SM_MODEL_DIR/model.joblib``.

Example:
    from sagemaker.estimator import Estimator
    Estimator(
        entry_point="train.py",
        image_uri="sagemaker-local:latest",
        hyperparameters={"dataset": "wine"},
    )
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
from sklearn.datasets import load_diabetes, load_wine
from xgboost import XGBClassifier, XGBRegressor

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

# dataset -> (task, loader). loaders return (X, y).
_DATASETS = {
    "diabetes": (
        "regression",
        lambda: (load_diabetes().data, load_diabetes().target),
    ),
    "wine": (
        "classification",
        lambda: (load_wine().data, load_wine().target),
    ),
}


def build_model(task: str) -> XGBRegressor | XGBClassifier:
    if task == "regression":
        return XGBRegressor(n_estimators=50)
    if task == "classification":
        return XGBClassifier(n_estimators=50, objective="multi:softprob")
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
    dataset = _parse_sm_hps().get("dataset", "diabetes")
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
