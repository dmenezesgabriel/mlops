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

    def test_clear_page_dependencies_drops_only_that_pages_deps(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        tracker = InMemoryDependencyTracker()
        page_a = Page(slug="a", title="A", source_path=tmp_path / "a.md")
        page_b = Page(slug="b", title="B", source_path=tmp_path / "b.md")
        tracker.register_dependency(page_a, tmp_path / "shared.yaml")
        tracker.register_dependency(page_a, tmp_path / "only_a.yaml")
        tracker.register_dependency(page_b, tmp_path / "shared.yaml")

        # Act
        tracker.clear_page_dependencies(page_a)

        # Assert — the shared path keeps its live member; the dead key is
        # evicted entirely instead of retaining a stale Page.
        assert tracker.affected_pages({tmp_path / "shared.yaml"}) == {page_b}
        assert tracker.affected_pages({tmp_path / "only_a.yaml"}) == set()
        assert len(tracker._dependencies) == 1
