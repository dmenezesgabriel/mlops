"""Unit tests for sagemaker_local.images."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

import pytest
from sagemaker_local import images


@dataclass
class FakeRunner:
    """Records subprocess calls; caller configures per-invocation behavior."""

    exit_codes: list[int]
    stdout: str = "built"
    stderr: str = ""
    calls: list[tuple[list[str], str]] = field(default_factory=list)

    def run(self, cmd: list[str], cwd: str | None = None, **_: object):
        self.calls.append((cmd, str(cwd or "")))
        code = self.exit_codes.pop(0)
        return subprocess.CompletedProcess(
            cmd, code, stdout=self.stdout.encode(), stderr=self.stderr.encode()
        )


def stub_build(runner: FakeRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(images, "_run_subprocess", runner.run)


class TestBuildImage:
    def test_invokes_docker_build_with_image_tag(self, monkeypatch):
        runner = FakeRunner(exit_codes=[0])
        stub_build(runner, monkeypatch)

        assert (
            images.build_image("sagemaker-local:latest")
            == "sagemaker-local:latest"
        )

        cmd, workdir = runner.calls[0]
        assert cmd[0:3] == ["docker", "build", "-t"]
        assert cmd[3] == "sagemaker-local:latest"
        assert workdir == str(images.dockerfile_dir())

    def test_raises_with_offending_tag_and_stderr(self, monkeypatch):
        runner = FakeRunner(exit_codes=[1], stderr="step 3 failed")
        stub_build(runner, monkeypatch)

        with pytest.raises(RuntimeError) as exc_info:
            images.build_image("sagemaker-local:latest")

        message = str(exc_info.value)
        assert "sagemaker-local:latest" in message
        assert "step 3 failed" in message

    def test_dockerfile_dir_points_at_docker_assets(self):
        assert (images.dockerfile_dir() / "Dockerfile").is_file()
        assert (images.dockerfile_dir() / "serve").is_file()
        assert (images.dockerfile_dir() / "serve_app.py").is_file()
