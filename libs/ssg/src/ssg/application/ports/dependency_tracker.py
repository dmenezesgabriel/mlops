from pathlib import Path
from typing import Protocol

from ssg.domain import Page


class DependencyTracker(Protocol):
    def register_dependency(self, page: Page, path: Path) -> None: ...

    def affected_pages(self, changed_paths: set[Path]) -> set[Page]: ...

    def clear_page_dependencies(self, page: Page) -> None: ...

    def clear(self) -> None: ...
