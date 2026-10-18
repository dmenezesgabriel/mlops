from typing import Protocol

from ssg.domain import (
    ContentCollection,
    PrecacheManifest,
    RenderedIndex,
    RenderedNotFound,
    RenderedPage,
    Site,
    SiteVariant,
)


class PageRenderer(Protocol):
    def render_page(self, rendered_page: RenderedPage) -> str: ...

    def render_index(self, rendered_index: RenderedIndex) -> str: ...

    def render_posts_index(self, rendered_index: RenderedIndex) -> str: ...

    def render_sitemap(
        self, site: Site, collections: tuple[ContentCollection, ...]
    ) -> str: ...

    def render_robots_txt(self, site: Site) -> str: ...

    def render_not_found(
        self, rendered_not_found: RenderedNotFound
    ) -> str: ...

    def render_service_worker(self, manifest: PrecacheManifest) -> str: ...

    def render_version_redirect(self, site: Site, target: str) -> str: ...

    def render_feed(
        self,
        site: Site,
        collection: ContentCollection,
        posts: tuple[RenderedPage, ...],
        variant: SiteVariant | None = None,
    ) -> str: ...

    def assets(self) -> dict[str, str]: ...
