"""SageMaker entrypoint: LightGBM regression on the California channel.

Reads every CSV in SM_CHANNEL_TRAIN, validates the feature contract,
trains an LGBMRegressor on an 80/20 split and writes model.joblib +
metrics.json into SM_MODEL_DIR.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pandas as pd
from joblib import dump
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, r2_score
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
    "n_estimators": 400,
    "learning_rate": 0.05,
    "num_leaves": 63,
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


def _validate(frame: pd.DataFrame) -> None:
    missing = [
        c for c in [*FEATURE_COLUMNS, LABEL_COLUMN] if c not in frame.columns
    ]
    if missing:
        msg = f"train channel missing columns {missing}; expected {FEATURE_COLUMNS + [LABEL_COLUMN]}"
        raise ValueError(msg)


def main() -> None:
    frame = _channel_frame()
    _validate(frame)
    x = frame[FEATURE_COLUMNS].astype(float)
    y = frame[LABEL_COLUMN].astype(float)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42
    )
    model = LGBMRegressor(**_parse_sm_hps(), random_state=42)
    model.fit(x_train, y_train)
    preds = model.predict(x_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, preds)),
        "r2": float(r2_score(y_test, preds)),
    }
    Path(MODEL_DIR).mkdir(parents=True, exist_ok=True)
    dump(model, Path(MODEL_DIR) / "model.joblib")
    (Path(MODEL_DIR) / "metrics.json").write_text(
        json.dumps(metrics, indent=2)
    )
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
