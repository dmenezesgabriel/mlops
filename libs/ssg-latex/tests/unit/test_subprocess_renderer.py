import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest
from ssg_latex.application.latex_processor import LatexRenderingError
from ssg_latex.infrastructure.subprocess_renderer import (
    SubprocessLatexRenderer,
)


class RecordedCommand(NamedTuple):
    args: list[str]
    input: str | None
    cwd: Path | None


class RecordingCommandRunner:
    """Named fake for the CommandRunner seam: replays queued results,
    raising any that are exceptions, and records every call."""

    def __init__(
        self,
        results: list[subprocess.CompletedProcess[str] | Exception],
    ) -> None:
        self._results = list(results)
        self.calls: list[RecordedCommand] = []

    def __call__(
        self,
        args: list[str],
        *,
        input: str | None = None,
        text: bool = False,
        capture_output: bool = False,
        check: bool = False,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(RecordedCommand(list(args), input, cwd))
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakePathLookup:
    """Named fake for `shutil.which`: fixed name→path map, records lookups."""

    def __init__(self, found: dict[str, str]) -> None:
        self._found = dict(found)
        self.calls: list[str] = []

    def __call__(self, name: str) -> str | None:
        self.calls.append(name)
        return self._found.get(name)


def make_package_dir(tmp_path: Path, *, with_katex_cli: bool) -> Path:
    package_dir = tmp_path / "pkg"
    katex_cli = package_dir / "node_modules" / "katex" / "cli.js"
    if with_katex_cli:
        katex_cli.parent.mkdir(parents=True)
        katex_cli.touch()
    else:
        package_dir.mkdir()
    return package_dir


def completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_renderer_raises_runtime_error_if_node_missing(tmp_path: Path) -> None:
    # Arrange
    renderer = SubprocessLatexRenderer(
        make_package_dir(tmp_path, with_katex_cli=True),
        run_command=RecordingCommandRunner([]),
        which=FakePathLookup({"npm": "/usr/bin/npm"}),
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="Node.js is required"):
        renderer.render("y = x", display_mode=False)


def test_renderer_raises_runtime_error_if_npm_missing(tmp_path: Path) -> None:
    # Arrange — npm is only required on the provisioning path, so the
    # vendored cli must be absent to reach the npm check.
    renderer = SubprocessLatexRenderer(
        make_package_dir(tmp_path, with_katex_cli=False),
        run_command=RecordingCommandRunner([]),
        which=FakePathLookup({"node": "/usr/bin/node"}),
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="npm is required"):
        renderer.render("y = x", display_mode=False)


def test_renderer_runs_npm_ci_if_katex_cli_missing(tmp_path: Path) -> None:
    # Arrange
    package_dir = make_package_dir(tmp_path, with_katex_cli=False)
    runner = RecordingCommandRunner(
        [
            completed(0, stdout="installed"),  # npm ci --ignore-scripts
            completed(0, stdout="HTML_RESULT"),  # node katex/cli.js
        ]
    )
    renderer = SubprocessLatexRenderer(
        package_dir,
        run_command=runner,
        which=FakePathLookup({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    # Act
    result = renderer.render("y = x", display_mode=False)

    # Assert — the first run provisions from the committed lockfile without
    # dependency lifecycle scripts, inside package_dir
    assert result == "HTML_RESULT"
    assert len(runner.calls) == 2
    assert runner.calls[0].args == ["npm", "ci", "--ignore-scripts"]
    assert runner.calls[0].cwd == package_dir


def test_renderer_invokes_katex_cli_via_node_when_provisioned(
    tmp_path: Path,
) -> None:
    # Arrange
    package_dir = make_package_dir(tmp_path, with_katex_cli=True)
    runner = RecordingCommandRunner([completed(0, stdout="HTML_RESULT")])
    renderer = SubprocessLatexRenderer(
        package_dir,
        run_command=runner,
        which=FakePathLookup({"node": "/usr/bin/node"}),
    )

    # Act
    result = renderer.render("y = x", display_mode=True)

    # Assert
    assert result == "HTML_RESULT"
    assert len(runner.calls) == 1
    assert runner.calls[0].args == [
        "node",
        str(package_dir / "node_modules" / "katex" / "cli.js"),
        "-d",
    ]


def test_renderer_does_not_require_npm_when_provisioned(
    tmp_path: Path,
) -> None:
    # Arrange — a node-only host with vendored node_modules renders fine:
    # npm is looked up only inside the provisioning branch.
    lookup = FakePathLookup({"node": "/usr/bin/node"})
    runner = RecordingCommandRunner([completed(0, stdout="HTML_RESULT")])
    renderer = SubprocessLatexRenderer(
        make_package_dir(tmp_path, with_katex_cli=True),
        run_command=runner,
        which=lookup,
    )

    # Act
    result = renderer.render("y = x", display_mode=False)

    # Assert
    assert result == "HTML_RESULT"
    assert lookup.calls == ["node"]
    assert len(runner.calls) == 1


def test_renderer_verifies_setup_once_across_renders(tmp_path: Path) -> None:
    # Arrange — the `_verified` flag must short-circuit repeated setup
    # checks: two renders = one PATH probe, two node invocations.
    lookup = FakePathLookup({"node": "/usr/bin/node"})
    runner = RecordingCommandRunner(
        [completed(0, stdout="A"), completed(0, stdout="B")]
    )
    renderer = SubprocessLatexRenderer(
        make_package_dir(tmp_path, with_katex_cli=True),
        run_command=runner,
        which=lookup,
    )

    # Act
    first = renderer.render("x", display_mode=False)
    second = renderer.render("y", display_mode=False)

    # Assert
    assert (first, second) == ("A", "B")
    assert lookup.calls == ["node"]
    assert len(runner.calls) == 2


def test_renderer_raises_runtime_error_if_npm_ci_fails(tmp_path: Path) -> None:
    # Arrange
    package_dir = make_package_dir(tmp_path, with_katex_cli=False)
    runner = RecordingCommandRunner(
        [
            subprocess.CalledProcessError(
                1, ["npm", "ci"], stderr=b"lockfile mismatch"
            )
        ]
    )
    renderer = SubprocessLatexRenderer(
        package_dir,
        run_command=runner,
        which=FakePathLookup({"node": "/usr/bin/node", "npm": "/usr/bin/npm"}),
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="npm ci") as exc_info:
        renderer.render("y = x", display_mode=False)
    assert str(package_dir) in str(exc_info.value)
    assert "lockfile mismatch" in str(exc_info.value)


def test_renderer_raises_latex_rendering_error_on_subprocess_failure(
    tmp_path: Path,
) -> None:
    # Arrange
    runner = RecordingCommandRunner(
        [completed(1, stderr="Invalid math expression")]
    )
    renderer = SubprocessLatexRenderer(
        make_package_dir(tmp_path, with_katex_cli=True),
        run_command=runner,
        which=FakePathLookup({"node": "/usr/bin/node"}),
    )

    # Act & Assert
    with pytest.raises(LatexRenderingError) as exc_info:
        renderer.render("invalid\\math", display_mode=False)

    assert "Failed to render LaTeX" in str(exc_info.value)
    assert "Invalid math expression" in str(exc_info.value)


def test_renderer_error_message_drops_node_stack_frames(
    tmp_path: Path,
) -> None:
    # Arrange — katex's uncaught ParseError prints the throwing file
    # location, the message line, `    at …` stack frames, then a
    # `{ position, rawMessage }` object dump. Only the message line is a
    # useful diagnostic in the user-facing error.
    katex_stderr = (
        "/pkg/node_modules/katex/dist/katex.js:17688\n"
        "    throw error;\n"
        "    ^\n"
        "\n"
        "ParseError: KaTeX parse error: Expected 'EOF', got '_' "
        "at position 8: \\text{a_{b}}\n"
        "    at Parser.expect (/pkg/node_modules/katex/dist/katex.js:16649:13)\n"
        "    at Parser.parseGroup (/pkg/node_modules/katex/dist/katex.js:17347:10) {\n"
        "  position: 8,\n"
        "  length: 1,\n"
        "  rawMessage: \"Expected 'EOF', got '_'\"\n"
        "}"
    )
    runner = RecordingCommandRunner([completed(1, stderr=katex_stderr)])
    renderer = SubprocessLatexRenderer(
        make_package_dir(tmp_path, with_katex_cli=True),
        run_command=runner,
        which=FakePathLookup({"node": "/usr/bin/node"}),
    )

    # Act & Assert
    with pytest.raises(LatexRenderingError) as exc_info:
        renderer.render("\\text{a_{b}}", display_mode=False)

    message = str(exc_info.value)
    assert "ParseError: KaTeX parse error" in message
    assert "Expected 'EOF', got '_'" in message
    assert "at Parser" not in message
    assert "rawMessage" not in message
    assert "katex.js" not in message
