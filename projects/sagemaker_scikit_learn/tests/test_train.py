"""Host-side tests for the image-bound ``train.py`` entrypoint.

Unlike the gradient-boosting examples, every import in
``sagemaker_scikit_learn.train`` resolves in the workspace (sklearn + joblib),
so it is imported directly — only the network-backed
``fetch_california_housing`` loader is replaced with a tiny fixture frame.
"""

import json
from pathlib import Path

import pytest
from sagemaker_scikit_learn import train as train_module
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.utils import Bunch


def _fake_california_housing() -> Bunch:
    # The real fetcher downloads from the network; a tiny Bunch keeps main()
    # fast and offline.
    return Bunch(
        data=[[1.0], [2.0], [3.0], [4.0]], target=[0.1, 0.2, 0.3, 0.4]
    )


def test_build_model_returns_ridge_pipeline_for_regression() -> None:
    # Act
    model = train_module.build_model("regression")

    # Assert
    assert isinstance(model, Pipeline)
    assert isinstance(model.named_steps["model"], Ridge)


def test_build_model_returns_logistic_pipeline_for_classification() -> None:
    # Act
    model = train_module.build_model("classification")

    # Assert
    assert isinstance(model, Pipeline)
    assert isinstance(model.named_steps["model"], LogisticRegression)


def test_build_model_rejects_unknown_task() -> None:
    # Act / Assert
    with pytest.raises(ValueError, match="unknown task"):
        train_module.build_model("unknown")


def test_main_trains_and_persists_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange: bundled sklearn loaders keep the data path real.
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": "breast_cancer"}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act
    train_module.main()

    # Assert
    assert (tmp_path / "model.joblib").is_file()


def test_main_defaults_to_california_housing_dataset(
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": "cifar"}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act / Assert
    with pytest.raises(ValueError, match="unsupported dataset"):
        train_module.main()
