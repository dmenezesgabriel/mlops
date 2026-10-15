"""Node subprocess renderer for Mermaid diagrams."""

import json
import shutil
import subprocess
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from typing import Protocol

from ssg_mermaid.application.mermaid_processor import (
    MermaidRenderer,
    MermaidRenderingError,
)

LOGGER = getLogger(__name__)


class CommandRunner(Protocol):
    """The `subprocess.run` surface this renderer uses — injectable so tests
    fake the boundary with named fakes instead of patching the module."""

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
        # The protocol documents the kwarg surface implementers must accept;
        # this body is the reference forward onto subprocess.run.
        return subprocess.run(
            args,
            input=input,
            text=text,
            capture_output=capture_output,
            check=check,
            cwd=cwd,
        )


def _mermaid_error_detail(stderr: str) -> str:
    # A mermaid parse failure dumps the message line plus `at …` stack
    # frames — only the `…Error:`/`Error:` line is a user-facing diagnostic.
    for line in stderr.splitlines():
        if "Error" in line:
            return line
    return next(
        (line for line in stderr.splitlines() if line.strip()),
        "unknown error",
    )


class SubprocessMermaidRenderer(MermaidRenderer):
    """Renderer that executes Mermaid via an external Node subprocess."""

    def __init__(
        self,
        package_dir: Path,
        run_command: CommandRunner = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.package_dir = package_dir
        self._run_command = run_command
        self._which = which
        self._render_script = package_dir / "render.mjs"
        self._dependency_marker = package_dir / "node_modules" / "mermaid"
        self._verified = False

    def render(self, source: str) -> str:
        self._ensure_setup()

        # Direct `node` on the vendored script, matching the latex
        # renderer: npx adds ~850 ms of npm machinery per call.
        cmd = ["node", str(self._render_script)]

        LOGGER.info(
            "subprocess_mermaid_renderer_rendering",
            extra={"context": {"source": source}},
        )

        result = self._run_command(
            cmd,
            input=json.dumps({"source": source}),
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            raise MermaidRenderingError(
                f"Failed to render Mermaid diagram {source!r}. "
                f"Error: {_mermaid_error_detail(result.stderr)}"
            )

        return self._parse_response(result.stdout, source)

    def _parse_response(self, stdout: str, source: str) -> str:
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise MermaidRenderingError(
                f"Mermaid renderer returned malformed output for {source!r}: "
                f"expected JSON with 'svg' or 'error', got {stdout.strip()!r}"
            ) from e
        if "error" in response:
            raise MermaidRenderingError(
                f"Failed to render Mermaid diagram {source!r}. "
                f"Error: {response['error']}"
            )
        svg = response.get("svg")
        if not isinstance(svg, str):
            raise MermaidRenderingError(
                f"Mermaid renderer returned malformed output for {source!r}: "
                f"expected key 'svg' of type str, got {response!r}"
            )
        return svg

    def _ensure_setup(self) -> None:
        if self._verified:
            return

        if not self._which("node"):
            raise RuntimeError(
                "Node.js is required to build Mermaid diagrams, but 'node' was not found on the system path. "
                "Please install Node.js (https://nodejs.org/) to proceed."
            )

        # Provision only when the vendored dependency tree is missing; npm
        # is needed solely for that install, so a node-only host with an
        # existing node_modules renders without it.
        if self._dependency_marker.exists():
            self._verified = True
            return

        if not self._which("npm"):
            raise RuntimeError(
                "npm is required to install Mermaid rendering dependencies, but 'npm' was not found on the system path. "
                "Please install Node.js (which includes npm) to proceed."
            )

        LOGGER.info(
            "subprocess_mermaid_renderer_installing_dependencies",
            extra={"context": {"package_dir": str(self.package_dir)}},
        )
        # `ci` honors the committed package-lock.json; --ignore-scripts keeps
        # dependency lifecycle hooks from executing inside the installed
        # package tree.
        try:
            self._run_command(
                ["npm", "ci", "--ignore-scripts"],
                cwd=self.package_dir,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to install Mermaid Node.js dependencies via `npm ci` inside {self.package_dir}. "
                f"Error: {e.stderr.decode('utf-8').strip()}"
            ) from e

        self._verified = True
