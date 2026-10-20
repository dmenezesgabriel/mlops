"""Host-side tests for the channel-based train.py entrypoint."""

import importlib
import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

MOD = "wine_quality_classification"
CONTRACT = importlib.import_module(f"{MOD}.feature_contract")
FEATURE_COLUMNS = CONTRACT.FEATURE_COLUMNS
LABEL_COLUMN = CONTRACT.LABEL_COLUMN


class _FakeModel:
    def __init__(self, **hps):
        self.hps = hps
        self.fitted = False

    def fit(self, x, y):
        self.fitted = True
        return self

    def predict(self, x):
        return np.zeros(len(x))

    def predict_proba(self, x):
        return np.tile([0.5, 0.5], (len(x), 1))


def _install_fake_framework(
    monkeypatch: pytest.MonkeyPatch,
) -> types.ModuleType:
    fake = types.ModuleType("fake_framework")
    for cls in ("LGBMRegressor", "CatBoostClassifier"):
        setattr(fake, cls, _FakeModel)
    fake.LogisticRegression = lambda **kw: _FakeModel(**kw)
    monkeypatch.setitem(sys.modules, "lightgbm", fake)
    monkeypatch.setitem(sys.modules, "catboost", fake)
    return fake


def _import_train(monkeypatch: pytest.MonkeyPatch):
    _install_fake_framework(monkeypatch)
    # sklearn bits train.py touches are real (present in workspace).
    return importlib.import_module(f"{MOD}.train")


def _channel_frame(rows: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    labels = (
        [i % 2 for i in range(rows)]
        if LABEL_COLUMN != "median_house_value"
        else rng.random(rows) * 5
    )
    if LABEL_COLUMN == "cultivar":
        labels = [i % 3 for i in range(rows)]
    return pd.DataFrame(
        {
            CONTRACT.ENTITY_COLUMN: [f"e{i}" for i in range(rows)],
            CONTRACT.TIMESTAMP_COLUMN: pd.to_datetime("2023-02-01", utc=True),
            LABEL_COLUMN: labels,
            **{c: rng.random(rows) for c in FEATURE_COLUMNS},
        }
    )


def test_main_writes_model_and_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _import_train(monkeypatch)
    channel = tmp_path / "channel"
    channel.mkdir()
    _channel_frame().to_csv(channel / "train.csv", index=False)
    model_dir = tmp_path / "model"
    monkeypatch.setattr(mod, "CHANNEL_DIR", channel)
    monkeypatch.setattr(mod, "MODEL_DIR", str(model_dir))
    mod.main()
    assert (model_dir / "model.joblib").exists()
    metrics = json.loads((model_dir / "metrics.json").read_text())
    assert metrics


def test_main_rejects_missing_columns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _import_train(monkeypatch)
    channel = tmp_path / "channel"
    channel.mkdir()
    _channel_frame().drop(columns=[FEATURE_COLUMNS[0]]).to_csv(
        channel / "train.csv", index=False
    )
    monkeypatch.setattr(mod, "CHANNEL_DIR", channel)
    monkeypatch.setattr(mod, "MODEL_DIR", str(tmp_path / "model"))
    with pytest.raises(ValueError, match="missing columns"):
        mod.main()


def test_main_rejects_empty_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _import_train(monkeypatch)
    channel = tmp_path / "empty"
    channel.mkdir()
    monkeypatch.setattr(mod, "CHANNEL_DIR", channel)
    monkeypatch.setattr(mod, "MODEL_DIR", str(tmp_path / "model"))
    with pytest.raises(FileNotFoundError):
        mod.main()
