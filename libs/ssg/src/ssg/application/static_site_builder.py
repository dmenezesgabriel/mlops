from pathlib import Path

from ssg.application.ports import ContentRenderer, PageRenderer, SiteRepository
from ssg.domain.site import ContentCollection, Page


class StaticSiteBuilder:
    def __init__(
        self,
        site_repository: SiteRepository,
        page_renderer: PageRenderer,
        content_renderers: tuple[ContentRenderer, ...],
    ) -> None:
        self._site_repository = site_repository
        self._page_renderer = page_renderer
        self._content_renderers = content_renderers

    def build(
        self, config_path: Path, output_path: Path, collection_name: str | None = None
    ) -> None:
        site = self._site_repository.load(config_path)
        for collection in site.selected_collections(collection_name):
            self._build_collection(collection, output_path)

    def _build_collection(self, collection: ContentCollection, output_path: Path) -> None:
        collection_output_path = output_path / collection.output_slug
        collection_output_path.mkdir(parents=True, exist_ok=True)

        for page in collection.pages:
            body = self._render_body(collection, page, collection_output_path)
            rendered_page = self._page_renderer.render_page(
                collection=collection,
                page_slug=page.slug,
                title=page.title,
                body=body,
            )
            (collection_output_path / f"{page.slug}.html").write_text(
                rendered_page,
                encoding="utf-8",
            )

    def _render_body(
        self,
        collection: ContentCollection,
        page: Page,
        output_path: Path,
    ) -> str:
        for renderer in self._content_renderers:
            if renderer.can_render(page.source_path):
                return renderer.render(collection, page, output_path)

        raise ValueError(
            f"Unsupported page source {page.source_path}: expected renderer for suffix "
            f"{page.source_path.suffix}",
        )
