from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ssg.domain.site import (
    Article,
    BuildContext,
    ContentCollection,
    Page,
    RenderedIndex,
    RenderedPage,
    Site,
    SiteVariant,
)


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


class DependencyTracker(Protocol):
    def register_dependency(self, page: Page, path: Path) -> None:
        pass

    def affected_pages(self, changed_paths: set[Path]) -> set[Page]:
        pass

    def clear(self) -> None:
        pass


class ContentRenderer(Protocol):
    def can_render(self, source_path: Path) -> bool:
        pass

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str:
        pass


class HtmlPostProcessor(Protocol):
    def process(self, rendered_html: str, site: Site) -> str:
        pass


class SiteVariantProvider(Protocol):
    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]:
        pass


class ArticleOutlineBuilder(Protocol):
    def build(self, title: str, body: str) -> Article:
        pass


class MarkdownRenderer(Protocol):
    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
    ) -> str:
        pass


class SiteReloader(Protocol):
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        on_change: Callable[[set[Path]], None],
        interval_seconds: float,
        ignored_paths: tuple[Path, ...] = (),
    ) -> None:
        pass


class PreviewServer(Protocol):
    def serve(self, directory: Path, host: str, port: int) -> None:
        pass
