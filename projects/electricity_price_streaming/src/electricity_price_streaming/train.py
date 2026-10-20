"""SageMaker entrypoint: CatBoost on the market-tick channel.

Reads every CSV in SM_CHANNEL_TRAIN, trains a direction classifier on an
80/20 split and writes model.joblib + metrics.json into SM_MODEL_DIR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pandas as pd
from catboost import CatBoostClassifier
from joblib import dump
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

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
DEFAULT_HPS: dict[str, int | float] = {
    "iterations": 300,
    "depth": 6,
    "learning_rate": 0.1,
}


def _parse_sm_hps() -> dict[str, int | float]:
    raw = os.environ.get("SM_HPS", "{}")
    decoded: object = json.loads(raw)
    if not isinstance(decoded, dict):
        msg = f"SM_HPS must be a JSON object, got {type(decoded).__name__}"
        raise ValueError(msg)
    provided = cast(dict[str, object], decoded)
    overrides = {
        name: value
        for name, value in provided.items()
        if name in DEFAULT_HPS and isinstance(value, (int, float))
    }
    return {**DEFAULT_HPS, **overrides}


def _channel_frame() -> pd.DataFrame:
    csvs = sorted(CHANNEL_DIR.glob("*.csv"))
    if not csvs:
        msg = f"no *.csv files found in train channel {CHANNEL_DIR}"
        raise FileNotFoundError(msg)
    return pd.concat([pd.read_csv(p) for p in csvs], ignore_index=True)


def main() -> None:
    frame = _channel_frame()
    missing = [
        c for c in [*FEATURE_COLUMNS, LABEL_COLUMN] if c not in frame.columns
    ]
    if missing:
        msg = f"train channel missing columns {missing}; expected {FEATURE_COLUMNS + [LABEL_COLUMN]}"
        raise ValueError(msg)
    x = frame[FEATURE_COLUMNS].astype(float)
    y = frame[LABEL_COLUMN].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42
    )
    model = CatBoostClassifier(**_parse_sm_hps(), random_state=42, verbose=0)
    model.fit(x_train, y_train)
    probs = model.predict_proba(x_test)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_test, model.predict(x_test))),
        "roc_auc": float(roc_auc_score(y_test, probs)),
    }
    Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)
    dump(model, Path(MODEL_DIR) / "model.joblib")
    (Path(MODEL_DIR) / "metrics.json").write_text(
        json.dumps(metrics, indent=2)
    )
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
