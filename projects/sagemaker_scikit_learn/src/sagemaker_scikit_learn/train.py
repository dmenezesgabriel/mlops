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
from sklearn.datasets import fetch_california_housing, load_breast_cancer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")

# dataset -> (task, loader). loaders return (X, y).
_DATASETS = {
    "california_housing": (
        "regression",
        lambda: fetch_california_housing(return_X_y=True),
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
