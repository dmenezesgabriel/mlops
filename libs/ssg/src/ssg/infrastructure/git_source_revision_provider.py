import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

from ssg.application.ports.source_revision_provider import (
    SourceRevisionProvider,
)


class GitSourceRevisionProvider(SourceRevisionProvider):
    """Revision facts from the git CLI.

    Every subprocess failure (no git binary, path outside any work tree,
    file with no history) reads as ``None`` so the rendered page omits the
    element — the same degrade as the starlight reference
    (`src/utils/git.ts`, `routing/data.ts` try/catch).
    """

    def __init__(self) -> None:
        self._repo_roots: dict[Path, Path | None] = {}

    def newest_commit_date(self, path: Path) -> date | None:
        output = self._git(
            path.parent,
            "log",
            "--format=%ct",
            "--max-count=1",
            "--",
            path.name,
        )
        if output is None or not output.isdigit():
            return None
        return datetime.fromtimestamp(int(output), UTC).date()

    def repository_path(self, path: Path) -> str | None:
        root = self._repo_root(path)
        if root is None:
            return None
        relative = os.path.relpath(path.resolve(), root)
        if relative.startswith(".."):
            return None
        return Path(relative).as_posix()

    def _repo_root(self, path: Path) -> Path | None:
        directory = path.parent.resolve()
        if directory not in self._repo_roots:
            output = self._git(directory, "rev-parse", "--show-toplevel")
            self._repo_roots[directory] = Path(output) if output else None
        return self._repo_roots[directory]

    def _git(self, directory: Path, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()
