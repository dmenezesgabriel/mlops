"""Host-side tests for the image-bound ``train.py`` entrypoint.

``xgboost`` is installed only inside the telco-customer-churn:train image
(see the DEP001 ignores in pyproject.toml), so these tests register named
fakes in ``sys.modules`` before importing ``telco_customer_churn.train`` —
pinning the channel/contract wiring and the SM_HPS/SM_MODEL_DIR contract
without the real framework. pandas/sklearn/joblib run for real.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import joblib
import numpy as np
import pandas as pd
import pytest
from telco_customer_churn.feature_contract import FEATURE_COLUMNS


class FakeXGBClassifier:
    """xgboost.XGBClassifier stand-in that records its fit() and hps."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.fitted = False

    def fit(self, x: object, y: object) -> FakeXGBClassifier:
        self.fitted = True
        return self

    def predict(self, x: object) -> np.ndarray:
        return np.zeros(len(x), dtype=int)

    def predict_proba(self, x: object) -> np.ndarray:
        rows = np.zeros((len(x), 2))
        rows[:, 1] = 0.5
        return rows


@pytest.fixture(scope="session", autouse=True)
def _fake_image_framework() -> None:
    # train.py executes `from xgboost import XGBClassifier` at import time;
    # installing the fake once keeps pandas/joblib import-cache state intact.
    fake_xgboost = ModuleType("xgboost")
    fake_xgboost.XGBClassifier = FakeXGBClassifier
    sys.modules["xgboost"] = fake_xgboost


@pytest.fixture(scope="session")
def train_module() -> ModuleType:
    return importlib.import_module("telco_customer_churn.train")


def _write_channel(tmp_path: Path, rows: int = 40) -> Path:
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "customer_id": [f"c{i}" for i in range(rows)],
            "event_timestamp": pd.to_datetime("2023-02-01", utc=True),
            # Alternating labels keep both classes in any contiguous holdout.
            "churn": [i % 2 for i in range(rows)],
            **{column: rng.random(rows) for column in FEATURE_COLUMNS},
        }
    )
    channel = tmp_path / "channel"
    channel.mkdir()
    frame.to_csv(channel / "train.csv", index=False)
    return channel


def test_build_model_forwards_hyperparameters(
    train_module: ModuleType,
) -> None:
    model = train_module.build_model(n_estimators=7, max_depth=2)
    assert type(model) is FakeXGBClassifier
    assert model.kwargs["n_estimators"] == 7
    assert model.kwargs["max_depth"] == 2


def test_int_setting_parses_numeric_strings_and_rejects_other_types(
    train_module: ModuleType,
) -> None:
    assert (
        train_module._int_setting({"n_estimators": "7"}, "n_estimators", 100)
        == 7
    )
    assert train_module._int_setting({}, "n_estimators", 100) == 100
    with pytest.raises(ValueError, match="must be an integer"):
        train_module._int_setting({"n_estimators": 1.5}, "n_estimators", 100)
    with pytest.raises(ValueError, match="must be an integer"):
        train_module._int_setting(
            {"n_estimators": "many"}, "n_estimators", 100
        )


def test_load_training_frame_rejects_missing_columns(
    train_module: ModuleType, tmp_path: Path
) -> None:
    channel = tmp_path / "channel"
    channel.mkdir()
    (channel / "train.csv").write_text("a,b\n1,2\n")
    old = train_module.CHANNEL_DIR
    train_module.CHANNEL_DIR = channel
    try:
        with pytest.raises(ValueError, match="missing required columns"):
            train_module.load_training_frame()
    finally:
        train_module.CHANNEL_DIR = old


def test_load_training_frame_rejects_empty_channel(
    train_module: ModuleType, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    old = train_module.CHANNEL_DIR
    train_module.CHANNEL_DIR = empty
    try:
        with pytest.raises(FileNotFoundError, match="no .csv files"):
            train_module.load_training_frame()
    finally:
        train_module.CHANNEL_DIR = old


def test_main_trains_and_writes_model_and_metrics(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _write_channel(tmp_path)
    model_dir = tmp_path / "model"
    monkeypatch.setenv("SM_CHANNEL_TRAIN", str(channel))
    monkeypatch.setenv("SM_MODEL_DIR", str(model_dir))
    monkeypatch.setenv(
        "SM_HPS", json.dumps({"n_estimators": 5, "max_depth": 2})
    )
    old_channel, old_dir = train_module.CHANNEL_DIR, train_module.MODEL_DIR
    train_module.CHANNEL_DIR = channel
    train_module.MODEL_DIR = str(model_dir)
    try:
        train_module.main()
    finally:
        train_module.CHANNEL_DIR = old_channel
        train_module.MODEL_DIR = old_dir

    model = joblib.load(model_dir / "model.joblib")
    assert type(model) is FakeXGBClassifier
    assert model.fitted
    metrics = json.loads((model_dir / "metrics.json").read_text())
    assert set(metrics) == {"accuracy", "auc"}
    assert 0.0 <= metrics["accuracy"] <= 1.0


def test_main_rejects_malformed_sm_hps(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    channel = _write_channel(tmp_path)
    monkeypatch.setenv("SM_HPS", "{not json")
    old_channel = train_module.CHANNEL_DIR
    train_module.CHANNEL_DIR = channel
    try:
        with pytest.raises(ValueError, match="SM_HPS is not valid JSON"):
            train_module.main()
    finally:
        train_module.CHANNEL_DIR = old_channel
