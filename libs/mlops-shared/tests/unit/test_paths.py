from pathlib import Path

import pytest
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


def test_repository_path_resolver_rejects_relative_path_escaping_root(
    tmp_path: Path,
) -> None:
    # Arrange
    resolver = RepositoryPathResolver(tmp_path / "repo")

    # Act / Assert
    with pytest.raises(ValueError, match="within repository root"):
        resolver.resolve("../outside")


def test_repository_path_resolver_normalizes_relative_path_within_root(
    tmp_path: Path,
) -> None:
    # Arrange
    resolver = RepositoryPathResolver(tmp_path)

    # Act
    resolved_path = resolver.resolve("sub/../inside")

    # Assert
    assert resolved_path == tmp_path / "inside"


def test_repository_path_resolver_normalizes_absolute_path(
    tmp_path: Path,
) -> None:
    # Arrange
    resolver = RepositoryPathResolver(tmp_path / "repo")

    # Act
    resolved_path = resolver.resolve(str(tmp_path / "a" / ".." / "b"))

    # Assert
    assert resolved_path == tmp_path / "b"
