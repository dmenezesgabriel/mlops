"""Fast, non-integration sanity checks for the example's local-mode wiring.

These need no docker, moto or a Jupyter kernel, so they run in the default
``make test`` gate. They pin the contract between the two Dockerfiles and the
batch-transform notebook: without this the training/inference images can drift
out of sync with what the notebook asks for.
"""

from __future__ import annotations

from pathlib import Path

# The framework line the inference Dockerfile must install.
INFERENCE_FRAMEWORK_LINE = "xgboost==2.1.4"

PROJECT_DIR = Path(__file__).resolve().parents[1]
IMAGE_TAG = "sagemaker-xgboost"
BATCH_NOTEBOOK = PROJECT_DIR / "notebooks" / "batch_transform.ipynb"


def _read(name: str) -> str:
    return (PROJECT_DIR / name).read_text(encoding="utf-8")


def test_train_image_serves_online_endpoints() -> None:
    dockerfile = _read("Dockerfile")
    assert "sagemaker-training==5.1.1" in dockerfile
    assert "COPY --chmod=0755 serve serve_app.py /opt/ml/serve/" in dockerfile


def test_inference_image_drops_training_toolkit() -> None:
    dockerfile_inference = _read("Dockerfile.inference")
    assert "sagemaker-training==5.1.1" not in dockerfile_inference
    assert (
        "COPY --chmod=0755 serve serve_app.py /opt/ml/serve/"
        in dockerfile_inference
    )


def test_inference_image_pins_framework() -> None:
    assert INFERENCE_FRAMEWORK_LINE in _read("Dockerfile.inference")


def test_batch_notebook_uses_matching_image_tags() -> None:
    notebook = BATCH_NOTEBOOK.read_text(encoding="utf-8")
    assert f"{IMAGE_TAG}:train" in notebook
    assert f"{IMAGE_TAG}:inference" in notebook
