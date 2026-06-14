from pathlib import Path
from typing import Protocol

from ssg.domain import BuildContext, ContentCollection, Page


class ContentRenderer(Protocol):
    def can_render(self, source_path: Path) -> bool: ...

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str: ...
