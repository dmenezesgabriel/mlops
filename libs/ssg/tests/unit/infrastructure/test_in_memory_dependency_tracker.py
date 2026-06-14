from pathlib import Path

from ssg.domain import Page
from ssg.infrastructure.in_memory_dependency_tracker import (
    InMemoryDependencyTracker,
)


class TestInMemoryDependencyTracker:
    def test_identifies_affected_pages(self, tmp_path: Path) -> None:
        # Arrange
        tracker = InMemoryDependencyTracker()
        page_a = Page(slug="a", title="A", source_path=tmp_path / "a.md")
        page_b = Page(slug="b", title="B", source_path=tmp_path / "b.md")

        # Act
        tracker.register_dependency(page_a, tmp_path / "shared.yaml")
        tracker.register_dependency(page_b, tmp_path / "shared.yaml")

        # Assert
        affected = tracker.affected_pages({tmp_path / "shared.yaml"})
        assert affected == {page_a, page_b}

    def test_clear_removes_dependencies(self, tmp_path: Path) -> None:
        # Arrange
        tracker = InMemoryDependencyTracker()
        page = Page(slug="a", title="A", source_path=tmp_path / "a.md")
        tracker.register_dependency(page, tmp_path / "shared.yaml")

        # Act
        tracker.clear()

        # Assert
        affected = tracker.affected_pages({tmp_path / "shared.yaml"})
        assert affected == set()
