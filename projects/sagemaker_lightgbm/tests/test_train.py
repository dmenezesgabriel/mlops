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


def _fake_california_housing(
    *args: object, **kwargs: object
) -> tuple[list[list[float]], list[float]]:
    # The real fetcher downloads from the network and is called with
    # return_X_y=True, so it yields a (data, target) tuple — a tiny frame
    # keeps main() fast and offline.
    return [[1.0], [2.0], [3.0], [4.0]], [0.1, 0.2, 0.3, 0.4]


class _CountingCaliforniaHousingFetch:
    """``fetch_california_housing`` stand-in that records its call count."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(
        self, *args: object, **kwargs: object
    ) -> tuple[list[list[float]], list[float]]:
        self.calls += 1
        return _fake_california_housing()


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


def test_build_model_declares_return_annotation(
    train_module: ModuleType,
) -> None:
    # Assert: pyright infers the return silently, so the declared annotation
    # is the parity contract with the scikit sibling (`-> Pipeline`).
    assert (
        train_module.build_model.__annotations__["return"]
        == "LGBMRegressor | LGBMClassifier"
    )


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


@pytest.mark.parametrize("raw_hps", ["not-json", "", "[1, 2]", "42"])
def test_main_rejects_invalid_sm_hps(
    raw_hps: str,
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("SM_HPS", raw_hps)
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act / Assert
    with pytest.raises(ValueError, match="SM_HPS"):
        train_module.main()


def test_main_rejects_non_string_dataset(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": ["x"]}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act / Assert
    with pytest.raises(ValueError, match="unsupported dataset"):
        train_module.main()


def test_main_fetches_california_housing_once(
    train_module: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    fetch = _CountingCaliforniaHousingFetch()
    monkeypatch.delenv("SM_HPS", raising=False)
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(train_module, "fetch_california_housing", fetch)

    # Act
    train_module.main()

    # Assert
    assert fetch.calls == 1
