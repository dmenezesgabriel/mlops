from collections import defaultdict
from pathlib import Path

from ssg.application.ports.dependency_tracker import DependencyTracker
from ssg.domain import Page


class InMemoryDependencyTracker(DependencyTracker):
    def __init__(self) -> None:
        self._dependencies: dict[Path, set[Page]] = defaultdict(set)
        self._registered_paths: dict[Page, set[Path]] = defaultdict(set)

    def register_dependency(self, page: Page, path: Path) -> None:
        resolved_path = path.resolve()
        self._dependencies[resolved_path].add(page)
        self._registered_paths[page].add(resolved_path)

    def affected_pages(self, changed_paths: set[Path]) -> set[Page]:
        affected: set[Page] = set()
        for changed_path in changed_paths:
            affected.update(
                self._dependencies.get(changed_path.resolve(), set())
            )
        return affected

    def clear_page_dependencies(self, page: Page) -> None:
        # Called before a page re-renders: its previous dep set is stale,
        # and keys left with no dependents must go or the persistent
        # tracker grows unboundedly across preview rebuilds.
        for registered_path in self._registered_paths.pop(page, set()):
            dependents = self._dependencies[registered_path]
            dependents.discard(page)
            if not dependents:
                del self._dependencies[registered_path]

    def clear(self) -> None:
        self._dependencies.clear()
        self._registered_paths.clear()
