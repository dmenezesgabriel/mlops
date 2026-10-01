from pathlib import Path
from typing import Protocol, runtime_checkable

from ssg.domain import BuildContext, ContentCollection, Page


@runtime_checkable
class ContentRenderer(Protocol):
    def can_render(self, source_path: Path) -> bool: ...

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str: ...
