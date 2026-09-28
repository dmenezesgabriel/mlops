"""Host-side tests for the image-bound ``train.py`` entrypoint.

``lightgbm`` is installed only inside the sagemaker-local training image (see
the DEP001 ignores in pyproject.toml), so these tests register named fakes in
``sys.modules`` before importing ``sagemaker_lightgbm.train`` — pinning the
dataset/task wiring and the SM_HPS/SM_MODEL_DIR contract without the real
framework. sklearn and joblib run for real.
"""

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sklearn.utils import Bunch


class FakeLGBMRegressor:
    """lightgbm.LGBMRegressor stand-in that records its fit()."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.fitted = False

    def fit(self, x: object, y: object) -> "FakeLGBMRegressor":
        self.fitted = True
        return self


class FakeLGBMClassifier(FakeLGBMRegressor):
    """lightgbm.LGBMClassifier stand-in."""


@pytest.fixture(scope="session", autouse=True)
def _fake_image_framework() -> None:
    # train.py executes `from lightgbm import ...` at import time; installing
    # the fake once keeps sklearn/joblib/numpy import-cache state intact.
    fake_lightgbm = ModuleType("lightgbm")
    fake_lightgbm.LGBMRegressor = FakeLGBMRegressor
    fake_lightgbm.LGBMClassifier = FakeLGBMClassifier
    sys.modules["lightgbm"] = fake_lightgbm


@pytest.fixture(scope="session")
def train_module() -> ModuleType:
    return importlib.import_module("sagemaker_lightgbm.train")


def _fake_california_housing() -> Bunch:
    # The real fetcher downloads from the network; a tiny Bunch keeps main()
    # fast and offline.
    return Bunch(
        data=[[1.0], [2.0], [3.0], [4.0]], target=[0.1, 0.2, 0.3, 0.4]
    )


def test_build_model_returns_regressor_for_regression(
    train_module: ModuleType,
) -> None:
    # Act
    model = train_module.build_model("regression")

    # Assert
    assert type(model) is FakeLGBMRegressor
    assert model.kwargs["n_estimators"] == 50


def test_build_model_returns_classifier_for_classification(
    train_module: ModuleType,
) -> None:
    # Act
    model = train_module.build_model("classification")

    # Assert
    assert type(model) is FakeLGBMClassifier


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
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": "iris"}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act
    train_module.main()

    # Assert
    assert (tmp_path / "model.joblib").is_file()


def test_main_defaults_to_california_housing_dataset(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.delenv("SM_HPS", raising=False)
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(
        train_module, "fetch_california_housing", _fake_california_housing
    )

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
