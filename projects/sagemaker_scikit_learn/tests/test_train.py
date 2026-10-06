"""Host-side tests for the image-bound ``train.py`` entrypoint.

Unlike the gradient-boosting examples, every import in
``sagemaker_scikit_learn.train`` resolves in the workspace (sklearn + joblib),
so it is imported directly — only the network-backed
``fetch_california_housing`` loader is replaced with a tiny fixture frame.
"""

import json
from pathlib import Path

import pytest
from joblib import load
from sagemaker_scikit_learn import train as train_module
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline


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
    assert model.named_steps["model"].max_iter == 1000


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

    # Assert: the artifact is the regression model — a flipped default would
    # persist the classification pipeline instead.
    model = load(tmp_path / "model.joblib")
    assert isinstance(model.named_steps["model"], Ridge)


def test_main_rejects_unsupported_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setenv("SM_HPS", json.dumps({"dataset": "cifar"}))
    monkeypatch.setattr(train_module, "MODEL_DIR", str(tmp_path))

    # Act / Assert: the full sorted list pins the message — a `sorted` drop
    # reorders it (insertion order: california_housing first).
    with pytest.raises(
        ValueError,
        match=r"expected one of \['breast_cancer', 'california_housing'\]",
    ):
        train_module.main()


@pytest.mark.parametrize("raw_hps", ["not-json", "", "[1, 2]", "42"])
def test_main_rejects_invalid_sm_hps(
    raw_hps: str,
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
