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
    def load(self, config_path: Path) -> Site: ...


class PageRenderer(Protocol):
    def render_page(self, rendered_page: RenderedPage) -> str: ...

    def render_index(self, rendered_index: RenderedIndex) -> str: ...

    def assets(self) -> dict[str, str]: ...


class DependencyTracker(Protocol):
    def register_dependency(self, page: Page, path: Path) -> None: ...

    def affected_pages(self, changed_paths: set[Path]) -> set[Page]: ...

    def clear(self) -> None: ...


class ContentRenderer(Protocol):
    def can_render(self, source_path: Path) -> bool: ...

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str: ...


class HtmlPostProcessor(Protocol):
    def process(self, rendered_html: str, site: Site) -> str: ...


class SiteVariantProvider(Protocol):
    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]: ...


class ArticleOutlineBuilder(Protocol):
    def build(self, title: str, body: str) -> Article: ...


class MarkdownRenderer(Protocol):
    def render_markdown(
        self,
        source: str,
        collection: ContentCollection,
        context: BuildContext,
        page: Page,
    ) -> str: ...


class SiteReloader(Protocol):
    def watch(
        self,
        watched_paths: tuple[Path, ...],
        on_change: Callable[[set[Path]], None],
        interval_seconds: float,
        ignored_paths: tuple[Path, ...] = (),
    ) -> None: ...


class PreviewServer(Protocol):
    def serve(self, directory: Path, host: str, port: int) -> None: ...
