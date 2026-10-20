"""Wiring checks for the wine_quality_classification project."""

from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_makefile_image_names_match_project() -> None:
    makefile = (PROJECT_DIR / "Makefile").read_text()
    assert "wine-quality-classification:train" in makefile


def test_compose_defines_namespaced_moto() -> None:
    compose = yaml.safe_load((PROJECT_DIR / "docker-compose.yml").read_text())
    assert (
        compose["services"]["moto"]["container_name"]
        == "wine-quality-classification-moto"
    )
    assert compose["networks"]["mlops_net"]["external"] is True


def test_local_config_points_at_project_moto() -> None:
    config = yaml.safe_load(
        (PROJECT_DIR / "configs" / "local.yaml").read_text()
    )
    assert (
        config["s3_endpoint_url"]
        == "http://wine-quality-classification-moto:5000"
    )
    assert config["bucket"] == "wine-quality-classification"
    assert config["serving_port"] == 8084


def test_feast_repo_is_offline_only() -> None:
    store = yaml.safe_load(
        (PROJECT_DIR / "feature_repo" / "feature_store.yaml").read_text()
    )
    assert store["offline_store"]["type"] == "duckdb"
    views = (PROJECT_DIR / "feature_repo" / "feature_views.py").read_text()
    assert "online=False" in views and "wine_assay_profile" in views


def test_feature_contract_has_13_measures() -> None:
    from wine_quality_classification.feature_contract import FEATURE_COLUMNS

    assert len(FEATURE_COLUMNS) == 13
