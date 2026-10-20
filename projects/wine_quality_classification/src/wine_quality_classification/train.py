"""SageMaker pipeline entrypoint: sklearn LogisticRegression on the wine
channel. Reads every CSV in SM_CHANNEL_TRAIN and writes model.joblib +
metrics.json into SM_MODEL_DIR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pandas as pd
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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

DEFAULT_HPS: dict[str, int | float] = {"C": 1.0, "max_iter": 1000}


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
        x, y, test_size=0.25, random_state=42, stratify=y
    )
    hps = _parse_sm_hps()
    model = make_pipeline(
        StandardScaler(), LogisticRegression(**hps, random_state=42)
    )
    model.fit(x_train, y_train)
    acc = float(accuracy_score(y_test, model.predict(x_test)))
    Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)
    dump(model, Path(MODEL_DIR) / "model.joblib")
    (Path(MODEL_DIR) / "metrics.json").write_text(
        json.dumps({"accuracy": acc}, indent=2)
    )
    print(json.dumps({"accuracy": acc}))


if __name__ == "__main__":
    main()
