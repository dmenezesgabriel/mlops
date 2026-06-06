from pathlib import Path

from ssg.application.dependency_tracker import InMemoryDependencyTracker
from ssg.domain.site import Page


class TestInMemoryDependencyTracker:
    def test_identifies_affected_pages(self, tmp_path: Path) -> None:
        # Arrange
        tracker = InMemoryDependencyTracker()
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )
        shared_script = tmp_path / "script.py"

        tracker.register_dependency(page1, page1.source_path)
        tracker.register_dependency(page2, page2.source_path)
        tracker.register_dependency(page1, shared_script)

        # Act
        affected_by_script = tracker.affected_pages({shared_script})
        affected_by_page2 = tracker.affected_pages({page2.source_path})
        affected_by_unknown = tracker.affected_pages({tmp_path / "unknown.md"})

        # Assert
        assert affected_by_script == {page1}
        assert affected_by_page2 == {page2}
        assert affected_by_unknown == set()

    def test_handles_multiple_changed_paths(self, tmp_path: Path) -> None:
        # Arrange
        tracker = InMemoryDependencyTracker()
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )

        tracker.register_dependency(page1, page1.source_path)
        tracker.register_dependency(page2, page2.source_path)

        # Act
        affected = tracker.affected_pages(
            {page1.source_path, page2.source_path}
        )

        # Assert
        assert affected == {page1, page2}

    def test_clears_graph(self, tmp_path: Path) -> None:
        # Arrange
        tracker = InMemoryDependencyTracker()
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        tracker.register_dependency(page1, page1.source_path)

        # Act
        tracker.clear()
        affected = tracker.affected_pages({page1.source_path})

        # Assert
        assert affected == set()
