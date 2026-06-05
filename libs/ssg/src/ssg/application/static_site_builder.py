from logging import getLogger
from pathlib import Path

from ssg.application.html_headings import HtmlArticleOutlineBuilder
from ssg.application.ports import (
    ArticleOutlineBuilder,
    ContentRenderer,
    PageRenderer,
    SiteRepository,
)
from ssg.domain.site import (
    ContentCollection,
    Page,
    PagerLink,
    RenderedIndex,
    RenderedPage,
    Site,
)

LOGGER = getLogger(__name__)


class StaticSiteBuilder:
    def __init__(
        self,
        site_repository: SiteRepository,
        page_renderer: PageRenderer,
        content_renderers: tuple[ContentRenderer, ...],
        article_outline_builder: ArticleOutlineBuilder | None = None,
    ) -> None:
        self._site_repository = site_repository
        self._page_renderer = page_renderer
        self._content_renderers = content_renderers
        self._article_outline_builder = article_outline_builder or HtmlArticleOutlineBuilder()

    def build(
        self, config_path: Path, output_path: Path, collection_name: str | None = None
    ) -> None:
        site = self._site_repository.load(config_path)
        selected_collections = site.selected_collections(collection_name)
        output_path.mkdir(parents=True, exist_ok=True)
        LOGGER.info(
            "site_build_started",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "collections": len(selected_collections),
                },
            },
        )
        self._write_assets(output_path)
        self._write_index(site, selected_collections, output_path)
        for collection in selected_collections:
            self._build_collection(site, collection, output_path)

        LOGGER.info(
            "site_build_finished",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "collections": len(selected_collections),
                },
            },
        )

    def _build_collection(
        self,
        site: Site,
        collection: ContentCollection,
        output_path: Path,
    ) -> None:
        collection_output_path = output_path / collection.output_slug
        collection_output_path.mkdir(parents=True, exist_ok=True)
        LOGGER.info(
            "collection_build_started",
            extra={
                "context": {
                    "collection": collection.name,
                    "output_path": str(collection_output_path),
                },
            },
        )

        for page in collection.pages:
            body = self._render_body(collection, page, collection_output_path)
            rendered_page = self._rendered_page(site, collection, page, body)
            rendered_html = self._page_renderer.render_page(rendered_page)
            output_file = collection_output_path / page.file_name()
            output_file.write_text(rendered_html, encoding="utf-8")
            LOGGER.info(
                "page_rendered",
                extra={
                    "context": {
                        "collection": collection.name,
                        "page_slug": page.slug,
                        "source_path": str(page.source_path),
                        "output_path": str(output_file),
                    },
                },
            )

    def _write_assets(self, output_path: Path) -> None:
        asset_path = output_path / "assets"
        asset_path.mkdir(parents=True, exist_ok=True)
        for file_name, source in self._page_renderer.assets().items():
            (asset_path / file_name).write_text(source, encoding="utf-8")

    def _write_index(
        self,
        site: Site,
        selected_collections: tuple[ContentCollection, ...],
        output_path: Path,
    ) -> None:
        rendered_index = RenderedIndex(
            site=site,
            collections=selected_collections,
            navigation=site.navigation_for(None, None),
        )
        index_path = output_path / "index.html"
        index_path.write_text(self._page_renderer.render_index(rendered_index), encoding="utf-8")
        LOGGER.info("site_index_rendered", extra={"context": {"output_path": str(index_path)}})

    def _rendered_page(
        self,
        site: Site,
        collection: ContentCollection,
        page: Page,
        body: str,
    ) -> RenderedPage:
        previous_page = collection.previous_page(page)
        next_page = collection.next_page(page)
        return RenderedPage(
            site=site,
            collection=collection,
            page=page,
            article=self._article_outline_builder.build(page.title, body),
            navigation=site.navigation_for(collection, page),
            previous_link=self._pager_link(previous_page, "Previous") if previous_page else None,
            next_link=self._pager_link(next_page, "Next") if next_page else None,
        )

    def _pager_link(self, page: Page, relation: str) -> PagerLink:
        return PagerLink(label=page.title, href=page.file_name(), relation=relation)

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
