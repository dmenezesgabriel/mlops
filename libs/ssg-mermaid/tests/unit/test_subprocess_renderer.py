"""Unit tests for the node-backed Mermaid renderer."""

import json
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

import pytest
from ssg_mermaid.application.mermaid_processor import MermaidRenderingError
from ssg_mermaid.infrastructure.subprocess_renderer import (
    SubprocessMermaidRenderer,
)


def completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=sys.executable,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class RecordingCommandRunner:
    def __init__(
        self, results: list[subprocess.CompletedProcess[str]]
    ) -> None:
        self.results = list(results)
        self.calls: list[unittest.mock._Call] = []

    def __call__(
        self, *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(unittest.mock.call(*args, **kwargs))
        return self.results.pop(0)


class FakePathLookup:
    def __init__(self, found: dict[str, str | None]) -> None:
        self.found = dict(found)
        self.checked: list[str] = []

    def __call__(self, name: str) -> str | None:
        self.checked.append(name)
        return self.found.get(name)


def make_package_dir(provisioned: bool = True) -> Path:
    package_dir = Path(tempfile.mkdtemp())
    if provisioned:
        (package_dir / "node_modules" / "mermaid").mkdir(parents=True)
    return package_dir


def test_node_missing_raises_actionable_error() -> None:
    # Arrange
    which = FakePathLookup({"node": None})
    renderer = SubprocessMermaidRenderer(
        Path("/nonexistent"),
        run_command=RecordingCommandRunner([]),
        which=which,
    )

    # Act / Assert
    with pytest.raises(RuntimeError, match="Node.js is required"):
        renderer.render("graph LR")


def test_npm_missing_when_unprovisioned_raises_actionable_error() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node", "npm": None})
    package_dir = make_package_dir(provisioned=False)
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=RecordingCommandRunner([]), which=which
    )

    # Act / Assert
    with pytest.raises(RuntimeError, match="npm is required"):
        renderer.render("graph LR")


def test_unprovisioned_installs_node_modules_then_renders() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node", "npm": "/usr/bin/npm"})
    package_dir = make_package_dir(provisioned=False)
    runner = RecordingCommandRunner(
        [completed(), completed(stdout='{"svg":"<svg></svg>"}')]
    )
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act
    svg = renderer.render("graph LR")

    # Assert
    assert svg == "<svg></svg>"
    assert len(runner.calls) == 2
    npm_call, node_call = runner.calls
    assert npm_call.args[0] == ["npm", "ci", "--ignore-scripts"]
    assert npm_call.kwargs["cwd"] == package_dir
    assert npm_call.kwargs["check"] is True
    assert node_call.args[0] == ["node", str(package_dir / "render.mjs")]
    assert json.loads(node_call.kwargs["input"]) == {"source": "graph LR"}


def test_provisioned_skips_npm_ci() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner(
        [completed(stdout='{"svg":"<svg></svg>"}')]
    )
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act
    renderer.render("graph LR")

    # Assert
    assert len(runner.calls) == 1
    assert which.checked == ["node"]


def test_dependencies_verified_once_per_renderer() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner(
        [
            completed(stdout='{"svg":"<svg></svg>"}'),
            completed(stdout='{"svg":"<svg></svg>"}'),
        ]
    )
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act
    renderer.render("graph LR")
    renderer.render("graph TD")

    # Assert
    assert which.checked == ["node"]


def test_npm_ci_failure_raises_runtime_error() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node", "npm": "/usr/bin/npm"})
    package_dir = make_package_dir(provisioned=False)

    def failing_run(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, args[0], stderr=b"404 mermaid")

    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=failing_run, which=which
    )

    # Act / Assert
    with pytest.raises(RuntimeError, match=str(package_dir)) as caught:
        renderer.render("graph LR")
    assert "404 mermaid" in str(caught.value)


def test_nonzero_exit_raises_mermaid_error_with_stderr_detail() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner(
        [completed(returncode=1, stderr="Error: Parse error on line 2")]
    )
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act / Assert
    with pytest.raises(MermaidRenderingError) as caught:
        renderer.render("graph ???")
    assert "Parse error on line 2" in str(caught.value)
    assert "graph ???" in str(caught.value)


def test_error_response_raises_mermaid_error() -> None:
    # Arrange — render.mjs reports a caught mermaid error on stdout.
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner(
        [completed(stdout='{"error":"Syntax error in graph"}')]
    )
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act / Assert
    with pytest.raises(MermaidRenderingError, match="Syntax error in graph"):
        renderer.render("graph ???")


def test_malformed_stdout_raises_mermaid_error() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner([completed(stdout="not json")])
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act / Assert
    with pytest.raises(MermaidRenderingError):
        renderer.render("graph LR")


def test_response_missing_svg_key_raises_mermaid_error() -> None:
    # Arrange
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner([completed(stdout="{}")])
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act / Assert
    with pytest.raises(MermaidRenderingError, match="'svg'"):
        renderer.render("graph LR")


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("segfault in worker", "segfault in worker"),
        ("", "unknown error"),
    ],
    ids=["non_error_line", "empty"],
)
def test_error_detail_falls_back_to_stderr_content(
    stderr: str, expected: str
) -> None:
    # Arrange — stderr without a recognizable `…Error` line still names
    # something actionable; empty stderr degrades to a fixed message.
    which = FakePathLookup({"node": "/usr/bin/node"})
    package_dir = make_package_dir(provisioned=True)
    runner = RecordingCommandRunner([completed(returncode=1, stderr=stderr)])
    renderer = SubprocessMermaidRenderer(
        package_dir, run_command=runner, which=which
    )

    # Act / Assert
    with pytest.raises(MermaidRenderingError, match=expected):
        renderer.render("graph LR")
