from collections import defaultdict
from pathlib import Path

from ssg.application.ports import DependencyTracker
from ssg.domain.site import Page


class InMemoryDependencyTracker(DependencyTracker):
    def __init__(self) -> None:
        self._dependencies: dict[Path, set[Page]] = defaultdict(set)

    def register_dependency(self, page: Page, path: Path) -> None:
        self._dependencies[path.resolve()].add(page)

    def affected_pages(self, changed_paths: set[Path]) -> set[Page]:
        affected: set[Page] = set()
        for changed_path in changed_paths:
            affected.update(self._dependencies.get(changed_path.resolve(), set()))
        return affected

    def clear(self) -> None:
        self._dependencies.clear()
