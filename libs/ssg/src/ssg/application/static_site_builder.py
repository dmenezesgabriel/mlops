import os
from logging import getLogger
from pathlib import Path
from uuid import uuid4

from ssg.application.dependency_tracker import InMemoryDependencyTracker
from ssg.application.html_headings import HtmlArticleOutlineBuilder
from ssg.application.ports import (
    ArticleOutlineBuilder,
    ContentRenderer,
    DependencyTracker,
    HtmlPostProcessor,
    PageRenderer,
    SiteRepository,
    SiteVariantProvider,
)
from ssg.domain.site import (
    BuildContext,
    ContentCollection,
    LanguageLink,
    Page,
    PagerLink,
    RenderedIndex,
    RenderedPage,
    Site,
    SiteVariant,
)

LOGGER = getLogger(__name__)


class SingleSiteVariantProvider(SiteVariantProvider):
    def variants(self, site: Site, context: BuildContext) -> tuple[SiteVariant, ...]:
        return (SiteVariant(site=site, output_path=context.output_path),)


class StaticSiteBuilder:
    def __init__(
        self,
        site_repository: SiteRepository,
        page_renderer: PageRenderer,
        content_renderers: tuple[ContentRenderer, ...],
        html_post_processors: tuple[HtmlPostProcessor, ...] = (),
        site_variant_provider: SiteVariantProvider | None = None,
        article_outline_builder: ArticleOutlineBuilder | None = None,
        dependency_tracker: DependencyTracker | None = None,
    ) -> None:
        self._site_repository = site_repository
        self._page_renderer = page_renderer
        self._content_renderers = content_renderers
        self._html_post_processors = html_post_processors
        self._site_variant_provider = site_variant_provider or SingleSiteVariantProvider()
        self._article_outline_builder = article_outline_builder or HtmlArticleOutlineBuilder()
        self._dependency_tracker = dependency_tracker or InMemoryDependencyTracker()

    def build(
        self,
        config_path: Path,
        output_path: Path,
        collection_name: str | None = None,
        changed_paths: set[Path] | None = None,
    ) -> None:
        if changed_paths is None or config_path.resolve() in [p.resolve() for p in changed_paths]:
            self._dependency_tracker.clear()
            affected_pages = None
        else:
            affected_pages = self._dependency_tracker.affected_pages(changed_paths)

        site = self._site_repository.load(config_path)
        base_selected_collections = site.selected_collections(collection_name)
        context = BuildContext(
            config_path=config_path,
            output_path=output_path,
            collection_name=collection_name,
            correlation_id=uuid4().hex,
            dependency_tracker=self._dependency_tracker,
        )
        site_variants = self._site_variant_provider.variants(site, context)
        LOGGER.info(
            "site_build_started",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "collections": len(base_selected_collections),
                    "variants": len(site_variants),
                    "correlation_id": context.correlation_id,
                    "incremental": affected_pages is not None,
                },
            },
        )
        for site_variant in site_variants:
            self._build_variant(
                site_variant, site_variants, collection_name, context, affected_pages
            )

        LOGGER.info(
            "site_build_finished",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "collections": len(base_selected_collections),
                    "variants": len(site_variants),
                    "correlation_id": context.correlation_id,
                },
            },
        )

    def _build_variant(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection_name: str | None,
        context: BuildContext,
        affected_pages: set[Page] | None = None,
    ) -> None:
        selected_collections = site_variant.site.selected_collections(collection_name)
        site_variant.output_path.mkdir(parents=True, exist_ok=True)
        LOGGER.info(
            "site_variant_build_started",
            extra={
                "context": {
                    "output_path": str(site_variant.output_path),
                    "locale": site_variant.site.locale,
                    "correlation_id": context.correlation_id,
                },
            },
        )
        self._write_assets(site_variant.output_path)
        self._write_index(site_variant, site_variants, selected_collections)
        for collection in selected_collections:
            self._build_collection(site_variant, site_variants, collection, context, affected_pages)

    def _build_collection(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection: ContentCollection,
        context: BuildContext,
        affected_pages: set[Page] | None = None,
    ) -> None:
        site = site_variant.site
        output_path = site_variant.output_path
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
            if affected_pages is not None and page not in affected_pages:
                LOGGER.info(
                    "page_build_skipped",
                    extra={
                        "context": {
                            "collection": collection.name,
                            "page_slug": page.slug,
                            "correlation_id": context.correlation_id,
                        },
                    },
                )
                continue

            body = self._render_body(site, collection, page, context)
            rendered_page = self._rendered_page(site_variant, site_variants, collection, page, body)
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
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        selected_collections: tuple[ContentCollection, ...],
    ) -> None:
        site = site_variant.site
        rendered_index = RenderedIndex(
            site=site,
            collections=selected_collections,
            navigation=site.navigation_for(None, None),
            language_links=self._index_language_links(site_variant, site_variants),
        )
        index_path = site_variant.output_path / "index.html"
        index_path.write_text(self._page_renderer.render_index(rendered_index), encoding="utf-8")
        LOGGER.info("site_index_rendered", extra={"context": {"output_path": str(index_path)}})

    def _rendered_page(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection: ContentCollection,
        page: Page,
        body: str,
    ) -> RenderedPage:
        site = site_variant.site
        previous_page = collection.previous_page(page)
        next_page = collection.next_page(page)
        return RenderedPage(
            site=site,
            collection=collection,
            page=page,
            article=self._article_outline_builder.build(page.title, body),
            navigation=site.navigation_for(collection, page),
            previous_link=self._pager_link(
                previous_page,
                site.extension_setting("i18n", "label_previous", "Previous"),
            )
            if previous_page
            else None,
            next_link=self._pager_link(
                next_page,
                site.extension_setting("i18n", "label_next", "Next"),
            )
            if next_page
            else None,
            language_links=self._page_language_links(site_variant, site_variants, collection, page),
        )

    def _pager_link(self, page: Page, relation: str) -> PagerLink:
        return PagerLink(label=page.title, href=page.file_name(), relation=relation)

    def _render_body(
        self,
        site: Site,
        collection: ContentCollection,
        page: Page,
        context: BuildContext,
    ) -> str:
        for renderer in self._content_renderers:
            if renderer.can_render(page.source_path):
                return self._process_rendered_html(renderer.render(collection, page, context), site)

        raise ValueError(
            f"Unsupported page source {page.source_path}: expected renderer for suffix "
            f"{page.source_path.suffix}",
        )

    def _process_rendered_html(self, rendered_html: str, site: Site) -> str:
        processed_html = rendered_html
        for post_processor in self._html_post_processors:
            processed_html = post_processor.process(processed_html, site)

        return processed_html

    def _index_language_links(
        self, current_variant: SiteVariant, site_variants: tuple[SiteVariant, ...]
    ) -> tuple[LanguageLink, ...]:
        return tuple(
            LanguageLink(
                label=site_variant.site.locale,
                href=self._relative_href(
                    current_variant.output_path,
                    site_variant.output_path / "index.html",
                ),
                current=site_variant.site.locale == current_variant.site.locale,
            )
            for site_variant in site_variants
        )

    def _page_language_links(
        self,
        current_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection: ContentCollection,
        page: Page,
    ) -> tuple[LanguageLink, ...]:
        current_directory = current_variant.output_path / collection.output_slug
        return tuple(
            self._page_language_link(
                current_variant, site_variant, current_directory, collection, page
            )
            for site_variant in site_variants
        )

    def _page_language_link(
        self,
        current_variant: SiteVariant,
        target_variant: SiteVariant,
        current_directory: Path,
        collection: ContentCollection,
        page: Page,
    ) -> LanguageLink:
        target_path = target_variant.output_path / collection.output_slug / page.file_name()
        return LanguageLink(
            label=target_variant.site.locale,
            href=self._relative_href(current_directory, target_path),
            current=target_variant.site.locale == current_variant.site.locale,
        )

    def _relative_href(self, current_directory: Path, target_path: Path) -> str:
        return Path(os.path.relpath(target_path, current_directory)).as_posix()
