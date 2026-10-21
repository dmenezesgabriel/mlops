"""Fast, non-integration sanity checks for the project's wiring.

These need no docker, moto or a Jupyter kernel, so they run in the default
``make test`` gate. They pin the contract between the Dockerfiles, the
compose stack, the Feast repo and the deploy notebook: without this the
training/inference images, the moto endpoint and the feature schema can
drift out of sync with what the notebooks ask for.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]
IMAGE_TAG = "telco-customer-churn"
DEPLOY_NOTEBOOK = PROJECT_DIR / "notebooks" / "deploy.ipynb"
DOCKER_CONTEXT = PROJECT_DIR.parent.parent / "libs/sagemaker-local/docker"

# The framework the inference image must install from its hashed lock.
INFERENCE_FRAMEWORK_LINE = "xgboost==2.1.4"


def _read(name: str) -> str:
    return (PROJECT_DIR / name).read_text(encoding="utf-8")


def _local_config() -> dict[str, object]:
    loaded = yaml.safe_load(_read("configs/local.yaml"))
    assert isinstance(loaded, dict)
    return loaded


def test_train_image_serves_online_endpoints() -> None:
    dockerfile = _read("Dockerfile")
    assert "requirements/telco-train.txt" in dockerfile
    assert "COPY --chmod=0755 serve serve_app.py /opt/ml/serve/" in dockerfile


def test_inference_image_drops_training_toolkit() -> None:
    dockerfile_inference = _read("Dockerfile.inference")
    assert "requirements/telco-inference.txt" in dockerfile_inference
    assert (
        "COPY --chmod=0755 serve serve_app.py /opt/ml/serve/"
        in dockerfile_inference
    )


def test_inference_image_pins_framework() -> None:
    lock = (DOCKER_CONTEXT / "requirements/telco-inference.txt").read_text()
    assert INFERENCE_FRAMEWORK_LINE in lock


def test_deploy_notebook_uses_matching_image_tags() -> None:
    notebook = DEPLOY_NOTEBOOK.read_text(encoding="utf-8")
    assert f"{IMAGE_TAG}:train" in notebook
    assert f"{IMAGE_TAG}:inference" in notebook


def test_compose_declares_project_moto() -> None:
    compose = yaml.safe_load(_read("docker-compose.yml"))
    moto = compose["services"]["moto"]
    assert moto["container_name"] == f"{IMAGE_TAG}-moto"
    assert compose["networks"]["mlops_net"]["external"] is True


def test_local_config_points_at_project_moto() -> None:
    cfg = _local_config()
    assert cfg["s3_endpoint_url"] == f"http://{IMAGE_TAG}-moto:5000"
    assert cfg["bucket"] == IMAGE_TAG
    # Each tutorial owns a unique serving port so stacks can run together.
    assert cfg["serving_port"] == 8081


def test_feature_repo_declares_offline_only_view() -> None:
    for name in (
        "feature_store.yaml",
        "entities.py",
        "data_sources.py",
        "feature_views.py",
    ):
        assert (PROJECT_DIR / "feature_repo" / name).is_file(), name
    views = _read("feature_repo/feature_views.py")
    assert "online=False" in views


def test_feature_contract_matches_view_schema() -> None:
    from telco_customer_churn.feature_contract import FEATURE_COLUMNS

    views = _read("feature_repo/feature_views.py")
    for column in FEATURE_COLUMNS:
        assert f'"{column}"' in views, (
            f"feature_contract column {column!r} missing from feature view"
        )


def test_prepare_data_writes_schema_consistently() -> None:
    schema_path = PROJECT_DIR / "data" / "processed" / "feature_schema.json"
    if not schema_path.is_file():
        return  # generated artifact — covered by test_prepare_data end-to-end
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    from telco_customer_churn.feature_contract import FEATURE_COLUMNS

    assert schema["features"] == FEATURE_COLUMNS
