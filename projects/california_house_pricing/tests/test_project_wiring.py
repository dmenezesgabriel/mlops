"""Wiring checks for the california_house_pricing project."""

from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_makefile_image_names_match_project() -> None:
    makefile = (PROJECT_DIR / "Makefile").read_text()
    assert "california-house-pricing:train" in makefile
    assert "california-house-pricing:inference" in makefile


def test_compose_defines_namespaced_moto() -> None:
    compose = yaml.safe_load((PROJECT_DIR / "docker-compose.yml").read_text())
    moto = compose["services"]["moto"]
    assert moto["container_name"] == "california-house-pricing-moto"
    assert "mlops_net" in moto["networks"]
    assert compose["networks"]["mlops_net"]["external"] is True


def test_local_config_points_at_project_moto() -> None:
    config = yaml.safe_load(
        (PROJECT_DIR / "configs" / "local.yaml").read_text()
    )
    assert (
        config["s3_endpoint_url"]
        == "http://california-house-pricing-moto:5000"
    )
    assert config["bucket"] == "california-house-pricing"
    assert config["serving_port"] == 8082


def test_feast_repo_uses_dynamodb_online_store() -> None:
    store = yaml.safe_load(
        (PROJECT_DIR / "feature_repo" / "feature_store.yaml").read_text()
    )
    assert store["online_store"]["type"] == "dynamodb"
    assert (
        store["online_store"]["endpoint_url"]
        == "http://california-house-pricing-moto:5000"
    )
    views = (PROJECT_DIR / "feature_repo" / "feature_views.py").read_text()
    assert "online=True" in views


def test_feature_contract_matches_train() -> None:
    contract = __import__(
        "california_house_pricing.feature_contract", fromlist=["x"]
    )
    train = (
        PROJECT_DIR / "src" / "california_house_pricing" / "train.py"
    ).read_text()
    assert "FEATURE_COLUMNS" in train and "LABEL_COLUMN" in train
    assert len(contract.FEATURE_COLUMNS) == 8
