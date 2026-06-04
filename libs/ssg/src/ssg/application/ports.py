from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ssg.domain.site import ContentCollection, Page, Site


class SiteRepository(Protocol):
    def load(self, config_path: Path) -> Site:
        pass


class PageRenderer(Protocol):
    def render_page(
        self,
        collection: ContentCollection,
        page_slug: str,
        title: str,
        body: str,
    ) -> str:
        pass


class ContentRenderer(Protocol):
    def can_render(self, source_path: Path) -> bool:
        pass

    def render(self, collection: ContentCollection, page: Page, output_path: Path) -> str:
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
