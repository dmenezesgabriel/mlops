from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ssg.domain.site import Article, ContentCollection, Page, RenderedIndex, RenderedPage, Site


class SiteRepository(Protocol):
    def load(self, config_path: Path) -> Site:
        pass


class PageRenderer(Protocol):
    def render_page(self, rendered_page: RenderedPage) -> str:
        pass

    def render_index(self, rendered_index: RenderedIndex) -> str:
        pass

    def assets(self) -> dict[str, str]:
        pass


class ContentRenderer(Protocol):
    def can_render(self, source_path: Path) -> bool:
        pass

    def render(self, collection: ContentCollection, page: Page, output_path: Path) -> str:
        pass


class HtmlPostProcessor(Protocol):
    def process(self, rendered_html: str, site: Site) -> str:
        pass


class ArticleOutlineBuilder(Protocol):
    def build(self, title: str, body: str) -> Article:
        pass


class MarkdownRenderer(Protocol):
    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        output_path: Path,
    ) -> str:
        pass


class SiteReloader(Protocol):
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        rebuild: Callable[[], None],
        interval_seconds: float,
    ) -> None:
        pass


class PreviewServer(Protocol):
    def serve(self, directory: Path, host: str, port: int) -> None:
        pass
