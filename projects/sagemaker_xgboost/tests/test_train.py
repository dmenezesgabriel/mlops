"""Host-side tests for the image-bound ``train.py`` entrypoint.

``xgboost`` is installed only inside the sagemaker-local training image (see
the DEP001 ignores in pyproject.toml), so these tests register named fakes in
``sys.modules`` before importing ``sagemaker_xgboost.train`` — pinning the
dataset/task wiring and the SM_HPS/SM_MODEL_DIR contract without the real
framework. sklearn and joblib run for real.
"""

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


class FakeXGBRegressor:
    """xgboost.XGBRegressor stand-in that records its fit()."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.fitted = False

    def fit(self, x: object, y: object) -> "FakeXGBRegressor":
        self.fitted = True
        return self


class FakeXGBClassifier(FakeXGBRegressor):
    """xgboost.XGBClassifier stand-in."""


@pytest.fixture(scope="session", autouse=True)
def _fake_image_framework() -> None:
    # train.py executes `from xgboost import ...` at import time; installing
    # the fake once keeps sklearn/joblib/numpy import-cache state intact.
    fake_xgboost = ModuleType("xgboost")
    fake_xgboost.XGBRegressor = FakeXGBRegressor
    fake_xgboost.XGBClassifier = FakeXGBClassifier
    sys.modules["xgboost"] = fake_xgboost


@pytest.fixture(scope="session")
def train_module() -> ModuleType:
    return importlib.import_module("sagemaker_xgboost.train")


def test_build_model_returns_regressor_for_regression(
    train_module: ModuleType,
) -> None:
    # Act
    model = train_module.build_model("regression")

    # Assert
    assert type(model) is FakeXGBRegressor
    assert model.kwargs["n_estimators"] == 50


def test_build_model_returns_classifier_for_classification(
    train_module: ModuleType,
) -> None:
    # Act
    model = train_module.build_model("classification")

    # Assert
    assert type(model) is FakeXGBClassifier


def test_build_model_rejects_unknown_task(train_module: ModuleType) -> None:
    # Act / Assert
    with pytest.raises(ValueError, match="unknown task"):
        train_module.build_model("unknown")


def test_main_trains_and_persists_model(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: bundled sklearn loaders keep the data path real.
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": "wine"}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act
    train_module.main()

    # Assert
    assert (tmp_path / "model.joblib").is_file()


def test_main_defaults_to_diabetes_dataset(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("SM_HPS", raising=False)
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act
    train_module.main()

    # Assert
    assert (tmp_path / "model.joblib").is_file()


def test_main_rejects_unsupported_dataset(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": "cifar"}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act / Assert
    with pytest.raises(ValueError, match="unsupported dataset"):
        train_module.main()
