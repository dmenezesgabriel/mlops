"""Training entry point run by SageMaker local mode inside the job container.

Invoked via the ``train`` console script (sagemaker-training) with
``SM_MODEL_DIR`` and ``SM_CHANNEL_TRAIN`` set by the SDK. Reads every CSV in
the ``train`` channel (uploaded to moto S3 by ``est.fit(inputs=...)`` and
bind-mounted here), trains on the declared feature columns and persists a
joblib model plus a metrics sidecar to ``SM_MODEL_DIR``.

The serving contract is a positional float matrix, so the ordered
``FEATURE_COLUMNS`` contract is enforced here at write time — column order
comes from the training file header itself.

Example (local mode):
    Estimator(
        entry_point="train.py",
        source_dir="src/telco_customer_churn",
        image_uri="telco-customer-churn:train",
    ).fit({"train": "s3://<bucket>/input/train/"})
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pandas as pd
from joblib import dump
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier

if TYPE_CHECKING:
    from .feature_contract import FEATURE_COLUMNS, LABEL_COLUMN
else:
    try:
        from .feature_contract import FEATURE_COLUMNS, LABEL_COLUMN
    except ImportError:  # flat layout under /opt/ml/code
        from feature_contract import FEATURE_COLUMNS, LABEL_COLUMN

MODEL_DIR = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
CHANNEL_DIR = Path(
    os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
)
HOLDOUT_FRACTION = 0.2


def build_model(n_estimators: int = 100, max_depth: int = 4) -> XGBClassifier:
    """Construct the classifier; ``n_estimators``/``max_depth`` arrive via SM_HPS."""
    return XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        eval_metric="logloss",
    )


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
    return cast(dict[str, object], hps)


def _int_setting(settings: dict[str, object], name: str, default: int) -> int:
    """Read an integer hyperparameter, accepting numeric strings from SM_HPS."""
    value = settings.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        msg = f"SM_HPS[{name!r}] must be an integer, got {value!r}"
        raise ValueError(msg)
    try:
        return int(value)
    except ValueError as exc:
        msg = f"SM_HPS[{name!r}] must be an integer, got {value!r}"
        raise ValueError(msg) from exc


def _channel_csvs() -> list[Path]:
    csvs = sorted(CHANNEL_DIR.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(
            f"no .csv files in train channel dir {CHANNEL_DIR}; "
            "expected at least one training CSV"
        )
    return csvs


def load_training_frame() -> pd.DataFrame:
    """Concatenate every CSV in the channel and verify the feature contract."""
    frame = pd.concat(
        (pd.read_csv(path) for path in _channel_csvs()), ignore_index=True
    )
    missing = [
        column
        for column in (*FEATURE_COLUMNS, LABEL_COLUMN)
        if column not in frame.columns
    ]
    if missing:
        raise ValueError(
            f"training CSV is missing required columns {missing}; "
            f"expected {sorted(FEATURE_COLUMNS + [LABEL_COLUMN])}"
        )
    return frame


def evaluate(
    model: XGBClassifier, x: pd.DataFrame, y: pd.Series
) -> dict[str, float]:
    """Holdout metrics persisted next to the model for the tuning stage."""
    return {
        "accuracy": float(accuracy_score(y, model.predict(x))),
        "auc": float(roc_auc_score(y, model.predict_proba(x)[:, 1])),
    }


def main() -> None:
    hps = _parse_sm_hps()
    frame = load_training_frame()
    split = int(len(frame) * (1 - HOLDOUT_FRACTION))
    shuffled = frame.sample(frac=1.0, random_state=42)
    train_frame, holdout = shuffled.iloc[:split], shuffled.iloc[split:]
    x_train = train_frame[FEATURE_COLUMNS].astype("float64")
    y_train = train_frame[LABEL_COLUMN].astype("int64")
    model = build_model(
        n_estimators=_int_setting(hps, "n_estimators", 100),
        max_depth=_int_setting(hps, "max_depth", 4),
    ).fit(x_train, y_train)
    metrics = evaluate(
        model,
        holdout[FEATURE_COLUMNS].astype("float64"),
        holdout[LABEL_COLUMN].astype("int64"),
    )
    os.makedirs(MODEL_DIR, exist_ok=True)
    dump(model, os.path.join(MODEL_DIR, "model.joblib"))
    (Path(MODEL_DIR) / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    print(f"metrics: {json.dumps(metrics)}")


if __name__ == "__main__":
    main()
