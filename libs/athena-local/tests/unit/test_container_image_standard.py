"""Contract tests for the root stack's built images.

The root compose stack builds the `jupyterlab` image from the root
Dockerfile and the Termux variant from `termux/Dockerfile`. ADR-0014 pins
every base by digest, labels every built image and feeds the revision from
the build. The checks are file reads: no docker daemon or proot-distro.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
ROOT_DOCKERFILE = REPO_ROOT / "Dockerfile"
TERMUX_DOCKERFILE = REPO_ROOT / "termux/Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
MAKEFILE = REPO_ROOT / "Makefile"
TERMUX_BUILD_SCRIPT = REPO_ROOT / "termux/build.sh"

UV_BASE = re.compile(
    r"^FROM ghcr\.io/astral-sh/uv:python3\.12-trixie-slim"
    r"@sha256:[0-9a-f]{64}$",
    re.MULTILINE,
)
LABEL_KEYS = [
    "org.opencontainers.image.title",
    "org.opencontainers.image.source",
    "org.opencontainers.image.revision",
    "org.opencontainers.image.licenses",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_base_is_pinned(dockerfile: Path) -> None:
    assert UV_BASE.search(_read(dockerfile)), (
        f"{dockerfile} must pin the uv base by digest"
    )


def _assert_oci_labels(dockerfile: Path) -> None:
    content = _read(dockerfile)
    assert "ARG GIT_REVISION=unknown" in content, (
        f"{dockerfile} must declare the revision build arg"
    )
    for key in LABEL_KEYS:
        assert key in content, f"{dockerfile} is missing {key}"


def _recipe(makefile: str, target: str) -> str:
    match = re.search(
        rf"^{target}:[^\n]*\n(?P<body>(?:\t[^\n]*\n)+)",
        makefile,
        re.MULTILINE,
    )
    assert match, f"Makefile has no recipe for {target}"
    return match.group("body")


def test_jupyterlab_base_is_pinned_by_digest() -> None:
    _assert_base_is_pinned(ROOT_DOCKERFILE)


def test_termux_base_is_pinned_by_digest() -> None:
    _assert_base_is_pinned(TERMUX_DOCKERFILE)


def test_jupyterlab_image_carries_oci_labels() -> None:
    _assert_oci_labels(ROOT_DOCKERFILE)


def test_termux_image_carries_oci_labels() -> None:
    _assert_oci_labels(TERMUX_DOCKERFILE)


def test_jupyterlab_build_passes_the_git_revision() -> None:
    loaded = yaml.safe_load(_read(COMPOSE_FILE))
    assert isinstance(loaded, dict), COMPOSE_FILE
    services = loaded["services"]
    assert isinstance(services, dict), COMPOSE_FILE
    build = services["jupyterlab"]["build"]
    assert isinstance(build, dict), COMPOSE_FILE
    assert build["context"] == "."
    assert build["args"]["GIT_REVISION"] == "${GIT_REVISION:-unknown}"
    recipe = _recipe(_read(MAKEFILE), "jupyterlab-build")
    expected = "GIT_REVISION=$(GIT_REVISION) docker compose build jupyterlab"
    assert expected in recipe


def test_termux_build_passes_the_git_revision() -> None:
    script = _read(TERMUX_BUILD_SCRIPT)
    assert "--build-arg GIT_REVISION=" in script
    assert 'git -C "$PROJECT_ROOT" rev-parse HEAD' in script
