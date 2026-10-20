"""Wiring checks for the electricity_price_streaming project."""

from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_compose_defines_streaming_stack() -> None:
    compose = yaml.safe_load((PROJECT_DIR / "docker-compose.yml").read_text())
    services = compose["services"]
    for name in ["moto", "kafka", "flink-jobmanager", "flink-taskmanager"]:
        assert name in services
    assert (
        services["moto"]["container_name"]
        == "electricity-price-streaming-moto"
    )
    assert compose["networks"]["mlops_net"]["external"] is True


def test_compose_caps_service_memory() -> None:
    # The JVMs size heap from host RAM unless pinned, so an idle stack could
    # commit gigabytes on a shared host. Every service needs a cgroup cap and
    # each JVM needs its heap/process size pinned under that cap.
    compose = yaml.safe_load((PROJECT_DIR / "docker-compose.yml").read_text())
    services = compose["services"]
    for name, service in services.items():
        limits = service["deploy"]["resources"]["limits"]
        assert limits["memory"], name
    kafka_heap = services["kafka"]["environment"]["KAFKA_HEAP_OPTS"]
    assert "-Xmx" in kafka_heap
    for role in ["flink-jobmanager", "flink-taskmanager"]:
        properties = services[role]["environment"]["FLINK_PROPERTIES"]
        assert "memory.process.size" in properties


def test_local_config_points_at_project_moto() -> None:
    config = yaml.safe_load(
        (PROJECT_DIR / "configs" / "local.yaml").read_text()
    )
    assert (
        config["s3_endpoint_url"]
        == "http://electricity-price-streaming-moto:5000"
    )
    assert config["serving_port"] == 8083


def test_feast_repo_uses_dynamodb_online() -> None:
    store = yaml.safe_load(
        (PROJECT_DIR / "feature_repo" / "feature_store.yaml").read_text()
    )
    assert store["online_store"]["type"] == "dynamodb"
    views = (PROJECT_DIR / "feature_repo" / "feature_views.py").read_text()
    assert "online=True" in views and "market_profile" in views


def test_flink_job_scores_from_the_tick_without_feast() -> None:
    # Feast's Kafka/stream sources are alpha and Feast does not ingest from a
    # topic; the tick already carries its market state, so the live scoring
    # path must not import or call Feast (Feast stays on the training join).
    job = (PROJECT_DIR / "flink_job" / "enrich_and_score.py").read_text()
    assert "from feast" not in job
    assert "FeatureStore" not in job
    assert "get_online_features" not in job
    assert "market-ticks" in job or "SOURCE_TOPIC" in job


def test_feature_contract_has_7_market_features() -> None:
    from electricity_price_streaming.feature_contract import FEATURE_COLUMNS

    assert FEATURE_COLUMNS == [
        "day",
        "period",
        "nswprice",
        "nswdemand",
        "vicprice",
        "vicdemand",
        "transfer",
    ]
