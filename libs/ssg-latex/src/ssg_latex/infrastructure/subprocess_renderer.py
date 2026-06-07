import shutil
import subprocess
from logging import getLogger
from pathlib import Path

from ssg_latex.application.latex_processor import (
    LatexRenderer,
    LatexRenderingError,
)

LOGGER = getLogger(__name__)


class SubprocessLatexRenderer(LatexRenderer):
    """Renderer that executes KaTeX via an external Node subprocess."""

    def __init__(self, package_dir: Path) -> None:
        self._package_dir = package_dir
        self._verified = False

    def render(self, expression: str, display_mode: bool) -> str:
        self._ensure_setup()

        cmd = [
            "npx",
            "--prefix",
            str(self._package_dir),
            "--no-install",
            "katex",
        ]
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

        result = subprocess.run(
            cmd,
            input=expression,
            text=True,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            raise LatexRenderingError(
                f"Failed to render LaTeX expression {expression!r}. "
                f"Error: {result.stderr.strip()}"
            )

        return result.stdout.strip()

    def _ensure_setup(self) -> None:
        if self._verified:
            return

        # Check if node is available
        if not shutil.which("node"):
            raise RuntimeError(
                "Node.js is required to build LaTeX math expressions, but 'node' was not found on the system path. "
                "Please install Node.js (https://nodejs.org/) to proceed."
            )

        # Check if npm is available
        if not shutil.which("npm"):
            raise RuntimeError(
                "npm is required to install LaTeX rendering dependencies, but 'npm' was not found on the system path. "
                "Please install Node.js (which includes npm) to proceed."
            )

        # Ensure dependencies are installed
        node_modules_dir = self._package_dir / "node_modules"
        if not node_modules_dir.exists():
            LOGGER.info(
                "subprocess_latex_renderer_installing_katex",
                extra={"context": {"package_dir": str(self._package_dir)}},
            )
            try:
                subprocess.run(
                    ["npm", "install"],
                    cwd=self._package_dir,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    f"Failed to install KaTeX Node.js dependencies via npm inside {self._package_dir}. "
                    f"Error: {e.stderr.decode('utf-8').strip()}"
                ) from e

        self._verified = True
