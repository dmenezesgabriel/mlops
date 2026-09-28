from pathlib import Path


class RepositoryPathResolver:
    """Resolve repository-relative paths from an explicit root.

    Example:
        RepositoryPathResolver(Path.cwd()).resolve("projects")
    """

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()

    def resolve(self, configured_path: str) -> Path:
        """Resolve a configured path against the repository root.

        Relative paths must stay inside the root after normalization —
        escapes raise ValueError (safe_join convention). Absolute paths are
        a deliberate opt-out of containment and are returned normalized.
        """
        path = Path(configured_path)
        if path.is_absolute():
            return path.resolve()

        resolved = (self._root_path / path).resolve()
        if not resolved.is_relative_to(self._root_path):
            raise ValueError(
                f"Invalid configured path {configured_path!r}: expected a path "
                f"within repository root {self._root_path}, resolved to {resolved}"
            )
        return resolved

    @property
    def root_path(self) -> Path:
        return self._root_path
