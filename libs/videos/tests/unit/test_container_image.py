"""Contract tests for the videos task image.

Both Makefile targets build this image from the repository root, so the
image standard (ADR-0014) is asserted here as file reads. No docker daemon
is needed: the built image is exercised by ``make test-videos-docker``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKERFILE = REPO_ROOT / "libs/videos/Dockerfile"
MAKEFILE = REPO_ROOT / "Makefile"

MANIM_BASE = re.compile(
    r"^FROM manimcommunity/manim:[^@\s]+@sha256:[0-9a-f]{64}$",
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
    assert MANIM_BASE.search(dockerfile), (
        "libs/videos/Dockerfile must pin manimcommunity/manim:v0.20.1 by digest"
    )


def test_uv_comes_from_the_pinned_image() -> None:
    dockerfile = _read(DOCKERFILE)
    assert UV_COPY.search(dockerfile), (
        "libs/videos/Dockerfile must copy uv from the pinned uv image"
    )
    assert "pip install uv" not in dockerfile, (
        "libs/videos/Dockerfile must not install uv from PyPI"
    )


def test_runtime_packages_install_non_editable() -> None:
    dockerfile = _read(DOCKERFILE)
    assert (
        "uv pip install --no-cache --no-editable libs/videos "
        "libs/videos-linter" in dockerfile
    ), "the runtime image must install its packages non-editable"
    assert not re.search(r"pip install .*(\s-e\s|--editable)", dockerfile), (
        "the runtime image must not install editable packages"
    )


def test_image_carries_the_oci_labels() -> None:
    dockerfile = _read(DOCKERFILE)
    assert "ARG GIT_REVISION=unknown" in dockerfile
    assert "${GIT_REVISION}" in dockerfile
    for key in LABEL_KEYS:
        assert key in dockerfile, f"libs/videos/Dockerfile is missing {key}"


def test_user_is_an_explicit_numeric_uid_gid() -> None:
    dockerfile = _read(DOCKERFILE)
    assert re.search(r"^USER 1000:1000$", dockerfile, re.MULTILINE), (
        "libs/videos/Dockerfile must declare USER 1000:1000"
    )


def test_render_target_runs_as_the_host_identity() -> None:
    makefile = _read(MAKEFILE)
    recipe = _recipe(makefile, "render-video")
    assert '--user "$(HOST_UID):$(HOST_GID)"' in recipe, (
        "render-video must pass the host UID/GID to docker run"
    )
    assert (
        '-v "$(abspath $(VIDEO_OUTPUT_DIR)):/app/output:delegated"' in recipe
    ), "render-video must mount the configured output directory"
    assert "chmod 777" not in recipe, (
        "render-video must not make the output directory world-writable"
    )
    assert "HOST_UID ?= $(shell id -u)" in makefile
    assert "HOST_GID ?= $(shell id -g)" in makefile


def test_both_builds_pass_the_git_revision() -> None:
    makefile = _read(MAKEFILE)
    build_args = "--build-arg GIT_REVISION=$(GIT_REVISION)"
    assert makefile.count(build_args) == 2, (
        "render-video and test-videos-docker must both label the build"
    )
    assert REVISION_DEFAULT in makefile
