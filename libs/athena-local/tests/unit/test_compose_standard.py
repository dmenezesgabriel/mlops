"""Contract tests for the compose service standard.

The root stack and the four project stacks are the repo's only compose
files; ADR-0014 pins every third-party reference by digest and caps every
service's memory. The checks are file reads: no docker daemon needed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILES = [
    REPO_ROOT / "docker-compose.yml",
    REPO_ROOT / "projects/california_house_pricing/docker-compose.yml",
    REPO_ROOT / "projects/electricity_price_streaming/docker-compose.yml",
    REPO_ROOT / "projects/telco_customer_churn/docker-compose.yml",
    REPO_ROOT / "projects/wine_quality_classification/docker-compose.yml",
]


def _services(compose_path: Path) -> dict[str, dict[str, object]]:
    loaded = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), compose_path
    services = loaded["services"]
    assert isinstance(services, dict), compose_path
    return services


def test_third_party_images_are_digest_pinned() -> None:
    for compose_path in COMPOSE_FILES:
        for name, service in _services(compose_path).items():
            if "build" in service:
                continue
            image = service["image"]
            assert isinstance(image, str), (compose_path, name)
            assert "@sha256:" in image, (compose_path, name, image)


def test_every_service_caps_memory() -> None:
    for compose_path in COMPOSE_FILES:
        for name, service in _services(compose_path).items():
            limits = service["deploy"]["resources"]["limits"]
            assert limits["memory"], (compose_path, name)
