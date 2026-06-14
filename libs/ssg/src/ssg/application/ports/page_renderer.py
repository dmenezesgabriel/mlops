from typing import Protocol

from ssg.domain import RenderedIndex, RenderedPage


class PageRenderer(Protocol):
    def render_page(self, rendered_page: RenderedPage) -> str: ...

    def render_index(self, rendered_index: RenderedIndex) -> str: ...

    def assets(self) -> dict[str, str]: ...
