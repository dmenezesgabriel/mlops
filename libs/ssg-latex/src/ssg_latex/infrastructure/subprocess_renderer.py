import shutil
import subprocess
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from typing import Protocol

from ssg_latex.application.latex_processor import (
    LatexRenderer,
    LatexRenderingError,
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


def _katex_error_detail(stderr: str) -> str:
    # katex's uncaught ParseError dumps the throwing file location, the
    # message line, `    at …` stack frames, then a `{ position, … }`
    # object dump — only the `…Error:` line is a user-facing diagnostic.
    for line in stderr.splitlines():
        if "Error:" in line:
            return line
    return next(
        (line for line in stderr.splitlines() if line.strip()),
        "unknown error",
    )


class SubprocessLatexRenderer(LatexRenderer):
    """Renderer that executes KaTeX via an external Node subprocess."""

    def __init__(
        self,
        package_dir: Path,
        run_command: CommandRunner = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.package_dir = package_dir
        self._run_command = run_command
        self._which = which
        self._katex_cli = package_dir / "node_modules" / "katex" / "cli.js"
        self._verified = False

    def render(self, expression: str, display_mode: bool) -> str:
        self._ensure_setup()

        # Direct `node` on the vendored CLI: npx wraps every call in ~850 ms
        # of npm machinery (1050-1374 ms vs 200-225 ms measured, Node 24).
        cmd = ["node", str(self._katex_cli)]
        if display_mode:
            cmd.append("-d")

        LOGGER.info(
            "subprocess_latex_renderer_rendering",
            extra={
                "context": {
                    "expression": expression,
                    "display_mode": display_mode,
                }
            },
        )

        result = self._run_command(
            cmd,
            input=expression,
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            raise LatexRenderingError(
                f"Failed to render LaTeX expression {expression!r}. "
                f"Error: {_katex_error_detail(result.stderr)}"
            )

        return result.stdout.strip()

    def _ensure_setup(self) -> None:
        if self._verified:
            return

        # Check if node is available
        if not self._which("node"):
            raise RuntimeError(
                "Node.js is required to build LaTeX math expressions, but 'node' was not found on the system path. "
                "Please install Node.js (https://nodejs.org/) to proceed."
            )

        # Provision only when the vendored CLI itself is missing; npm is
        # needed solely for that install, so a node-only host with an
        # existing node_modules renders without it.
        if self._katex_cli.exists():
            self._verified = True
            return

        if not self._which("npm"):
            raise RuntimeError(
                "npm is required to install LaTeX rendering dependencies, but 'npm' was not found on the system path. "
                "Please install Node.js (which includes npm) to proceed."
            )

        LOGGER.info(
            "subprocess_latex_renderer_installing_katex",
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
                f"Failed to install KaTeX Node.js dependencies via `npm ci` inside {self.package_dir}. "
                f"Error: {e.stderr.decode('utf-8').strip()}"
            ) from e

        self._verified = True
