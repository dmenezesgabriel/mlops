"""Contract tests for the diagrams task image.

The Makefile builds the image from ``libs/diagrams``, so the image standard
(ADR-0014) is asserted here as file reads and the gate needs no docker
daemon. ``make test-diagrams-docker`` runs this suite inside the image,
where the repository checkout is absent; there the module skips and the
host gate remains the authority.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPOSITORY_MARKER = Path("libs/diagrams/Dockerfile")


def _find_repository_root() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if (parent / _REPOSITORY_MARKER).is_file():
            return parent
    return None


REPOSITORY_ROOT = _find_repository_root()
if REPOSITORY_ROOT is None:
    pytest.skip(
        "the image contract is asserted from the repository checkout",
        allow_module_level=True,
    )

DOCKERFILE = REPOSITORY_ROOT / "libs/diagrams/Dockerfile"
MAKEFILE = REPOSITORY_ROOT / "Makefile"

PYTHON_BASE = re.compile(
    r"^FROM python:[^@\s]+@sha256:[0-9a-f]{64}$",
    re.MULTILINE,
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
REVISION_DEFAULT = (
    "GIT_REVISION ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _recipe(makefile: str, target: str) -> str:
    match = re.search(
        rf"^{target}:[^\n]*\n(?P<body>(?:\t[^\n]*\n)+)",
        makefile,
        re.MULTILINE,
    )
    assert match, f"Makefile has no recipe for {target}"
    return match.group("body")


def test_base_is_pinned_to_a_manifest_digest() -> None:
    dockerfile = _read(DOCKERFILE)
    assert PYTHON_BASE.search(dockerfile), (
        "libs/diagrams/Dockerfile must pin python:3.11-slim by digest"
    )


def test_uv_comes_from_the_pinned_image() -> None:
    dockerfile = _read(DOCKERFILE)
    assert UV_COPY.search(dockerfile), (
        "libs/diagrams/Dockerfile must copy uv from the pinned uv image"
    )
    assert "pip install uv" not in dockerfile, (
        "libs/diagrams/Dockerfile must not install uv from PyPI"
    )


def test_runtime_packages_install_non_editable() -> None:
    dockerfile = _read(DOCKERFILE)
    assert (
        'uv pip install --system --no-cache --no-editable ".[diagrams]"'
        in dockerfile
    ), "the runtime image must install its package non-editable"
    assert not re.search(r"pip install .*(\s-e\s|--editable)", dockerfile), (
        "the runtime image must not install editable packages"
    )


def test_image_carries_the_test_runner() -> None:
    dockerfile = _read(DOCKERFILE)
    assert "pytest==9.0.3" in dockerfile, (
        "libs/diagrams/Dockerfile must install the test runner"
    )
    assert "pytest-bdd==8.1.0" in dockerfile, (
        "libs/diagrams/Dockerfile must install the BDD plugin"
    )


def test_image_carries_the_oci_labels() -> None:
    dockerfile = _read(DOCKERFILE)
    assert "ARG GIT_REVISION=unknown" in dockerfile
    assert "${GIT_REVISION}" in dockerfile
    for key in LABEL_KEYS:
        assert key in dockerfile, f"libs/diagrams/Dockerfile is missing {key}"


def test_user_is_an_explicit_numeric_uid_gid() -> None:
    dockerfile = _read(DOCKERFILE)
    assert re.search(r"^USER 1000:1000$", dockerfile, re.MULTILINE), (
        "libs/diagrams/Dockerfile must declare USER 1000:1000"
    )


def test_render_target_runs_as_the_host_identity() -> None:
    makefile = _read(MAKEFILE)
    recipe = _recipe(makefile, "diagrams-render")
    assert '--user "$(HOST_UID):$(HOST_GID)"' in recipe, (
        "diagrams-render must pass the host UID/GID to docker run"
    )
    assert "chmod 777" not in recipe, (
        "diagrams-render must not make the output directory world-writable"
    )
    assert "HOST_UID ?= $(shell id -u)" in makefile
    assert "HOST_GID ?= $(shell id -g)" in makefile


def test_both_builds_pass_the_git_revision() -> None:
    makefile = _read(MAKEFILE)
    build_args = "--build-arg GIT_REVISION=$(GIT_REVISION)"
    for target in ("diagrams-build", "test-diagrams-docker"):
        assert build_args in _recipe(makefile, target), (
            f"{target} must label the build with GIT_REVISION"
        )
    assert REVISION_DEFAULT in makefile
