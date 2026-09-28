"""Tests for the shared pinned Go SDK test runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from tests.integration import _terraform_harness


class RecordingGoRunner:
    """Capture a Go subprocess invocation without launching Go."""

    def __init__(self) -> None:
        self.command: list[str] = []
        self.environment: dict[str, str] = {}
        self.cwd: Path | None = None

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert timeout > 0
        self.command = command
        self.environment = env
        self.cwd = cwd
        return subprocess.CompletedProcess(command, 0, "", "")


def test_run_go_test_preserves_service_endpoint_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Endpoint variables reach the pinned SDK process unchanged."""
    runner = RecordingGoRunner()
    monkeypatch.setattr(_terraform_harness.subprocess, "run", runner)
    endpoint_environment = {
        "AWS_ENDPOINT_URL": "http://moto:5000",
        "AWS_ENDPOINT_URL_ATHENA": "http://athena:5001",
    }

    _terraform_harness.run_go_test(
        Path("/usr/bin/go"),
        "TestEndpointRouting",
        endpoint_environment,
    )

    assert runner.cwd == _terraform_harness.GO_MODULE
    assert runner.command[1:3] == ["test", "-run"]
    assert "AWS_ENDPOINT_URL" in runner.environment
    assert runner.environment["AWS_ENDPOINT_URL_ATHENA"] == (
        "http://athena:5001"
    )


class RecordingTerraformRunner:
    """Capture a terraform subprocess invocation without launching it."""

    def __init__(self, returncode: int) -> None:
        self.command: list[str] = []
        self.environment: dict[str, str] = {}
        self.cwd: Path | None = None
        self.returncode = returncode

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        assert capture_output is True
        assert text is True
        assert timeout > 0
        self.command = command
        self.environment = env
        self.cwd = cwd
        return subprocess.CompletedProcess(command, self.returncode, "", "")


def test_terraform_binary_prefers_environment_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    override = tmp_path / "terraform"
    override.touch()
    monkeypatch.setenv("ATHENA_TERRAFORM_BINARY", str(override))

    assert _terraform_harness.terraform_binary() == override
    assert _terraform_harness.require_terraform_binary() == override


def test_terraform_binary_rejects_a_nonfile_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ATHENA_TERRAFORM_BINARY", str(tmp_path / "missing"))

    with pytest.raises(pytest.fail.Exception):
        _terraform_harness.terraform_binary()


def test_require_terraform_binary_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATHENA_TERRAFORM_BINARY", raising=False)
    monkeypatch.delenv("ATHENA_TERRAFORM_REQUIRED", raising=False)
    monkeypatch.setattr(_terraform_harness.shutil, "which", lambda name: None)

    with pytest.raises(pytest.skip.Exception):
        _terraform_harness.require_terraform_binary()

    monkeypatch.setenv("ATHENA_TERRAFORM_REQUIRED", "1")
    with pytest.raises(pytest.fail.Exception):
        _terraform_harness.require_terraform_binary()


def test_run_terraform_returns_the_process_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A nonzero exit (e.g. ``plan -detailed-exitcode`` drift) is data, not
    an immediate test failure."""
    runner = RecordingTerraformRunner(returncode=2)
    monkeypatch.setattr(_terraform_harness.subprocess, "run", runner)
    variables = {"TF_VAR_bucket": "results-bucket"}

    result = _terraform_harness.run_terraform(
        Path("/usr/bin/terraform"),
        ["plan", "-detailed-exitcode"],
        tmp_path,
        variables,
    )

    assert result.returncode == 2
    assert runner.command[1:] == ["plan", "-detailed-exitcode"]
    assert runner.cwd == tmp_path
    assert runner.environment["TF_VAR_bucket"] == "results-bucket"
