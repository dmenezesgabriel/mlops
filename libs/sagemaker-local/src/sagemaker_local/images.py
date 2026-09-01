"""Build the combined training/serving docker image used by local mode."""

from __future__ import annotations

import subprocess
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_run_subprocess = subprocess.run


def dockerfile_dir() -> Path:
    """Directory containing the Dockerfile and serve assets.

    Assets ship inside the source tree (repo workspace installs); this path
    does not resolve from an installed wheel.
    """
    return _PACKAGE_ROOT / "docker"


def build_image(tag: str = "sagemaker-local:latest") -> str:
    """Build the local-mode image under ``tag``; returns the tag on success.

    Example:
        >>> build_image()  # doctest: +SKIP
        'sagemaker-local:latest'
    """
    result = _run_subprocess(
        ["docker", "build", "-t", tag, "."],
        capture_output=True,
        cwd=dockerfile_dir(),
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"docker build failed for tag {tag!r} in {dockerfile_dir()}: "
            f"{result.stderr.decode(errors='replace')}"
        )
    return tag
