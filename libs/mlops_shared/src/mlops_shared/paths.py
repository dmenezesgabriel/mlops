from pathlib import Path


class RepositoryPathResolver:
    """Resolve repository-relative paths from an explicit root.

    Example:
        RepositoryPathResolver(Path.cwd()).resolve("projects")
    """

    def __init__(self, root_path: Path) -> None:
        self._root_path = root_path.resolve()

    def resolve(self, configured_path: str) -> Path:
        path = Path(configured_path)
        if path.is_absolute():
            return path

        return (self._root_path / path).resolve()

    @property
    def root_path(self) -> Path:
        return self._root_path
