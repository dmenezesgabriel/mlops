"""Contract tests for the streaming stack's PyFlink image.

The stock Flink image ships no Python, so the mounted ``flink_job`` cannot
run there. These checks assert the image standard (ADR-0014) as file reads:
no docker daemon is needed, and ``make quality`` keeps the contract honest.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[1]
DOCKERFILE = PROJECT_DIR / "docker" / "flink" / "Dockerfile"
REQUIREMENTS = PROJECT_DIR / "docker" / "flink" / "requirements.txt"
COMPOSE = PROJECT_DIR / "docker-compose.yml"
JOB = PROJECT_DIR / "flink_job" / "enrich_and_score.py"
MAKEFILE = PROJECT_DIR / "Makefile"

FLINK_BASE = (
    "flink:1.20-scala_2.12-java11"
    "@sha256:671e890a10e783374d626a6870756c6ad86983e8f94e8a21b6d1408a1f86be2c"
)
UV_COPY = re.compile(
    r"^COPY --from=ghcr\.io/astral-sh/uv:[^@\s]+@sha256:[0-9a-f]{64} "
    r"/uv /uvx /usr/local/bin/$",
    re.MULTILINE,
)
LABEL_KEYS = [
    "org.opencontainers.image.title",
    "org.opencontainers.image.source",
    "org.opencontainers.image.revision",
    "org.opencontainers.image.licenses",
]
CONNECTOR = "flink-sql-connector-kafka-3.4.0-1.20.jar"
CONNECTOR_SHA256 = (
    "b860724fd97d7da0901bfc3859680442f4c1aa2b35ab944407558b393a1cf93e"
)
FLINK_ROLES = ("flink-jobmanager", "flink-taskmanager")
ENDPOINT_URL = "${SAGEMAKER_ENDPOINT_URL:-}"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _services() -> dict[str, dict[str, object]]:
    loaded = yaml.safe_load(_read(COMPOSE))
    assert isinstance(loaded, dict), COMPOSE
    services = loaded["services"]
    assert isinstance(services, dict), COMPOSE
    return services


def _recipe(makefile: str, target: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:[^\n]*\n(?P<body>(?:\t[^\n]*\n)+)",
        makefile,
        re.MULTILINE,
    )
    assert match, f"Makefile has no recipe for {target}"
    return match.group("body")


def test_base_is_the_pinned_flink_manifest_digest() -> None:
    assert f"FROM {FLINK_BASE}" in _read(DOCKERFILE), (
        "the streaming image must extend the digest-pinned Flink base"
    )


def test_image_carries_the_four_oci_labels() -> None:
    dockerfile = _read(DOCKERFILE)
    assert "ARG GIT_REVISION=unknown" in dockerfile
    assert "${GIT_REVISION}" in dockerfile
    for key in LABEL_KEYS:
        assert key in dockerfile, f"the Flink image is missing {key}"


def test_uv_comes_from_the_pinned_image() -> None:
    dockerfile = _read(DOCKERFILE)
    assert UV_COPY.search(dockerfile), (
        "the Flink image must copy uv from the pinned uv image"
    )
    assert "pip install uv" not in dockerfile, (
        "the Flink image must not install uv from PyPI"
    )


def test_pyflink_installs_from_a_hashed_lock() -> None:
    dockerfile = _read(DOCKERFILE)
    requirements = _read(REQUIREMENTS)
    assert "--require-hashes" in dockerfile
    assert "apache-flink==1.20.5" in requirements
    assert "--hash=sha256:" in requirements
    assert "apache-flink==" in dockerfile or "requirements.txt" in dockerfile


def test_kafka_connector_is_checksum_pinned_into_the_flink_lib() -> None:
    dockerfile = _read(DOCKERFILE)
    assert f"--checksum=sha256:{CONNECTOR_SHA256}" in dockerfile
    assert f"/opt/flink/lib/{CONNECTOR}" in dockerfile


def test_kafka_connector_is_readable_by_the_flink_user() -> None:
    dockerfile = _read(DOCKERFILE)
    assert "--chmod=644" in dockerfile, (
        "ADD from a URL defaults to mode 600 root:root; uid 9999 must read "
        "the connector jar"
    )


def test_image_runs_as_the_upstream_flink_user() -> None:
    assert re.search(r"^USER 9999:9999$", _read(DOCKERFILE), re.MULTILINE), (
        "the Flink image must run as the base image's flink user"
    )


def test_both_roles_build_the_local_image() -> None:
    services = _services()
    for role in FLINK_ROLES:
        service = services[role]
        build = service["build"]
        assert isinstance(build, dict), role
        assert build["context"] == "./docker/flink", role
        assert build["args"]["GIT_REVISION"] == "${GIT_REVISION:-unknown}", (
            role
        )
        assert service["image"] == "electricity-price-streaming:flink", role


def test_both_roles_expose_the_endpoint_url() -> None:
    services = _services()
    for role in FLINK_ROLES:
        environment = services[role]["environment"]
        assert isinstance(environment, dict), role
        assert environment["SAGEMAKER_ENDPOINT_URL"] == ENDPOINT_URL, role


def test_job_uses_the_connector_bundled_in_the_image() -> None:
    job = _read(JOB)
    assert "add_jars" not in job, (
        "the Kafka connector ships in /opt/flink/lib; a client-side glob "
        "would never be expanded by the JVM"
    )


def test_makefile_builds_with_the_git_revision() -> None:
    makefile = _read(MAKEFILE)
    build = _recipe(makefile, "flink-image")
    assert "GIT_REVISION=$(GIT_REVISION)" in build
    assert "build flink-jobmanager" in build
    assert "GIT_REVISION=$(GIT_REVISION)" in _recipe(makefile, "up-%")
