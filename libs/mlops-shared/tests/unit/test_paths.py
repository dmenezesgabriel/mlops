from pathlib import Path

from mlops_shared.paths import RepositoryPathResolver


def test_repository_path_resolver_resolves_relative_path(
    tmp_path: Path,
) -> None:
    # Arrange
    resolver = RepositoryPathResolver(tmp_path)

    # Act
    resolved_path = resolver.resolve("projects/example")

    # Assert
    assert resolved_path == tmp_path / "projects" / "example"
