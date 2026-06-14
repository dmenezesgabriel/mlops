from typing import Protocol

from ssg.domain import BuildContext, ContentCollection, Page


class MarkdownRenderer(Protocol):
    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
    ) -> str: ...
