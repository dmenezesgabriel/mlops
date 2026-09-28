"""Shared runners for the pinned AWS SDK for Go v2 contract tests and the
real terraform CLI lifecycle test."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

GO_MODULE = Path(__file__).parents[1] / "terraform"
GO_TEST_TIMEOUT_SECONDS = 180.0
TERRAFORM_MODULE = GO_MODULE / "apply"
TERRAFORM_COMMAND_TIMEOUT_SECONDS = 600.0
TERRAFORM_PLUGIN_CACHE = GO_MODULE / ".plugin-cache"


def go_binary() -> Path | None:
    """Return the configured or discoverable Go binary, if one exists."""
    configured = os.environ.get("ATHENA_GO_BINARY")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        pytest.fail(f"ATHENA_GO_BINARY does not point to a file: {configured}")
    discovered = shutil.which("go")
    return Path(discovered) if discovered is not None else None


def require_go_binary() -> Path:
    """Return Go or enforce the suite's explicit optional-tool policy."""
    binary = go_binary()
    if binary is not None:
        return binary
    if os.environ.get("ATHENA_GO_REQUIRED") == "1":
        pytest.fail("Go toolchain is required but was not found")
    pytest.skip("Go toolchain unavailable; set PATH or ATHENA_GO_BINARY")


def run_go_test(
    binary: Path,
    test_name: str,
    environment: Mapping[str, str],
) -> None:
    """Run one named Go test with caller-owned AWS endpoint variables."""
    process_environment = {
        **os.environ,
        "GOFLAGS": "-mod=readonly",
        "GOTOOLCHAIN": "local",
        **environment,
    }
    command = [
        str(binary),
        "test",
        "-run",
        f"^{test_name}$",
        "-count=1",
        "-v",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=GO_MODULE,
            env=process_environment,
            capture_output=True,
            text=True,
            timeout=GO_TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(f"Go test {test_name!r} timed out: {error}")
    if result.returncode == 0:
        return
    pytest.fail(
        f"Go test {test_name!r} failed:\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def terraform_binary() -> Path | None:
    """Return the configured or discoverable terraform binary, if one exists."""
    configured = os.environ.get("ATHENA_TERRAFORM_BINARY")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        pytest.fail(
            f"ATHENA_TERRAFORM_BINARY does not point to a file: {configured}"
        )
    discovered = shutil.which("terraform")
    return Path(discovered) if discovered is not None else None


def require_terraform_binary() -> Path:
    """Return terraform or enforce the suite's explicit optional-tool policy."""
    binary = terraform_binary()
    if binary is not None:
        return binary
    if os.environ.get("ATHENA_TERRAFORM_REQUIRED") == "1":
        pytest.fail("terraform CLI is required but was not found")
    pytest.skip(
        "terraform CLI unavailable; set PATH or ATHENA_TERRAFORM_BINARY"
    )


def run_terraform(
    binary: Path,
    arguments: list[str],
    working_directory: Path,
    environment: Mapping[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run one terraform command, returning the process for exit-code checks.

    Unlike ``run_go_test`` this never fails on the exit code: ``plan
    -detailed-exitcode`` uses 2 as a meaningful verdict (drift present) that
    the caller must inspect.
    """
    process_environment = {**os.environ, **environment}
    command = [str(binary), *arguments]
    try:
        return subprocess.run(
            command,
            cwd=working_directory,
            env=process_environment,
            capture_output=True,
            text=True,
            timeout=TERRAFORM_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(f"terraform {arguments!r} timed out: {error}")
