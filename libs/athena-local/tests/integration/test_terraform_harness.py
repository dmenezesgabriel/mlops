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
