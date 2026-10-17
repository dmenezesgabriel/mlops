import shutil
from dataclasses import replace
from datetime import UTC, date, datetime
from logging import getLogger
from pathlib import Path
from uuid import uuid4

from ssg.application.offline_precache import precache_manifest
from ssg.application.ports.article_outline_builder import ArticleOutlineBuilder
from ssg.application.ports.content_renderer import ContentRenderer
from ssg.application.ports.dependency_tracker import DependencyTracker
from ssg.application.ports.html_post_processor import HtmlPostProcessor
from ssg.application.ports.page_renderer import PageRenderer
from ssg.application.ports.search_index import SearchIndex
from ssg.application.ports.site_repository import SiteRepository
from ssg.application.ports.site_variant_provider import SiteVariantProvider
from ssg.application.ports.social_card_renderer import SocialCardRenderer
from ssg.application.ports.source_revision_provider import (
    SourceRevisionProvider,
)
from ssg.application.variant_links import (
    absolute_navigation,
    index_language_links,
    not_found_language_links,
    page_language_links,
)
from ssg.application.version_links import (
    not_found_version_links,
    version_links_for,
)
from ssg.application.versioned_output import (
    emission_segments,
    finalize_versioned_output,
    prepare_versioned_output,
)
from ssg.domain import (
    BuildContext,
    ContentCollection,
    Page,
    PagerLink,
    RenderedIndex,
    RenderedNotFound,
    RenderedPage,
    Site,
    SiteVariant,
    SocialCard,
    alternate_links_for,
)
from ssg.domain.readtime import calculate_readtime_minutes

LOGGER = getLogger(__name__)


class StaticSiteBuilder:
    """Use Case for compiling configured content collections into static pages."""

    def __init__(
        self,
        site_repository: SiteRepository,
        page_renderer: PageRenderer,
        content_renderers: tuple[ContentRenderer, ...],
        site_variant_provider: SiteVariantProvider,
        article_outline_builder: ArticleOutlineBuilder,
        dependency_tracker: DependencyTracker,
        search_index: SearchIndex,
        html_post_processors: tuple[HtmlPostProcessor, ...] = (),
        source_revision_provider: SourceRevisionProvider | None = None,
        social_card_renderer: SocialCardRenderer | None = None,
    ) -> None:
        self._site_repository = site_repository
        self._page_renderer = page_renderer
        self._content_renderers = content_renderers
        self._html_post_processors = html_post_processors
        self._site_variant_provider = site_variant_provider
        self._article_outline_builder = article_outline_builder
        self._dependency_tracker = dependency_tracker
        self._search_index = search_index
        self._source_revision_provider = source_revision_provider
        self._social_card_renderer = social_card_renderer

    def build(
        self,
        config_path: Path,
        output_path: Path,
        collection_name: str | None = None,
        changed_paths: set[Path] | None = None,
    ) -> None:
        if changed_paths is None or config_path.resolve() in [
            p.resolve() for p in changed_paths
        ]:
            self._dependency_tracker.clear()
            self._search_index.clear()
            affected_pages = None
        else:
            affected_pages = self._dependency_tracker.affected_pages(
                changed_paths
            )

        site = self._site_repository.load(config_path)
        base_selected_collections = site.selected_collections(collection_name)
        context = BuildContext(
            config_path=config_path,
            output_path=output_path,
            collection_name=collection_name,
            correlation_id=uuid4().hex,
            dependency_tracker=self._dependency_tracker,
        )
        segments = emission_segments(site)
        LOGGER.info(
            "site_build_started",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "collections": len(base_selected_collections),
                    "version_segments": len(segments),
                    "correlation_id": context.correlation_id,
                    "incremental": affected_pages is not None,
                },
            },
        )
        if site.versioning is not None:
            prepare_versioned_output(output_path, site.versioning)
        for segment in segments:
            self._build_segment(
                site,
                segment,
                output_path,
                collection_name,
                context,
                affected_pages,
            )
        if site.versioning is not None:
            finalize_versioned_output(
                output_path,
                site.versioning,
                self._page_renderer.render_version_redirect(
                    site, site.versioning.default_version_id()
                ),
            )

        LOGGER.info(
            "site_build_finished",
            extra={
                "context": {
                    "output_path": str(output_path),
                    "collections": len(base_selected_collections),
                    "version_segments": len(segments),
                    "correlation_id": context.correlation_id,
                },
            },
        )

    def _build_segment(
        self,
        site: Site,
        segment: str,
        output_path: Path,
        collection_name: str | None,
        context: BuildContext,
        affected_pages: set[Page] | None,
    ) -> None:
        # One segment = one output dir: "" resolves to the build root for
        # the unversioned layout, the version id otherwise. Locale
        # variants nest inside it.
        segment_site = replace(site, version=segment)
        segment_context = replace(context, output_path=output_path / segment)
        site_variants = self._site_variant_provider.variants(
            segment_site, segment_context
        )
        for site_variant in site_variants:
            self._build_variant(
                site_variant,
                site_variants,
                collection_name,
                segment_context,
                affected_pages,
            )

    def _build_variant(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection_name: str | None,
        context: BuildContext,
        affected_pages: set[Page] | None = None,
    ) -> None:
        selected_collections = site_variant.site.selected_collections(
            collection_name
        )
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
        self._write_assets(site_variant)
        self._write_index(site_variant, site_variants, selected_collections)
        variant_context = replace(
            context, output_path=site_variant.output_path
        )
        for collection in selected_collections:
            self._build_collection(
                site_variant,
                site_variants,
                collection,
                variant_context,
                affected_pages,
            )
        self._search_index.write(site_variant.output_path)
        self._write_sitemap(site_variant, selected_collections)
        self._write_robots_txt(site_variant)
        self._write_not_found(
            site_variant, site_variants, selected_collections
        )
        self._write_service_worker(site_variant, site_variants)

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

            self._dependency_tracker.clear_page_dependencies(page)
            body = self._render_body(site, collection, page, context)
            social_image = self._write_social_card(
                site_variant,
                SocialCard(
                    site_title=site.title,
                    eyebrow=collection.title,
                    title=page.title,
                    description=site.description,
                    locale=site.locale,
                ),
                f"assets/social/{collection.output_slug}/{page.slug}.png",
            )
            rendered_page = self._rendered_page(
                site_variant,
                site_variants,
                collection,
                page,
                body,
                social_image,
            )
            location = f"{collection.output_slug}/{page.file_name()}"
            self._search_index.update_page(
                output_path,
                location,
                rendered_page.article.search_entries(location),
            )
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
        if collection.is_dated_posts:
            self._emit_posts_artifacts(
                site_variant,
                site_variants,
                collection,
                affected_pages,
                context,
            )

    def _emit_posts_artifacts(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection: ContentCollection,
        affected_pages: set[Page] | None,
        context: BuildContext,
    ) -> None:
        posts = self._prepare_posts(
            collection, site_variant, site_variants, context
        )
        collection_output_path = (
            site_variant.output_path / collection.output_slug
        )
        collection_output_path.mkdir(parents=True, exist_ok=True)
        site = site_variant.site
        rendered_index = RenderedIndex(
            site=site,
            collections=(
                ContentCollection(
                    name=collection.name,
                    title=collection.title,
                    source_root=collection.source_root,
                    output_slug=collection.output_slug,
                    pages=tuple(post.page for post in posts),
                    videos=collection.videos,
                    images=collection.images,
                    kind=collection.kind,
                ),
            ),
            navigation=site.navigation_for(
                None, None, collections=(collection,)
            ),
            language_links=index_language_links(site_variant, site_variants),
            version_links=version_links_for(
                site_variant, site_variant.output_path / collection.output_slug
            ),
            alternate_links=alternate_links_for(
                site_variants, f"{collection.output_slug}/"
            ),
        )
        index_path = collection_output_path / "index.html"
        index_path.write_text(
            self._page_renderer.render_index(rendered_index), encoding="utf-8"
        )
        feed_path = collection_output_path / "feed.xml"
        feed_path.write_text(
            self._page_renderer.render_feed(site, collection, posts),
            encoding="utf-8",
        )

    def _prepare_posts(
        self,
        collection: ContentCollection,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        context: BuildContext,
    ) -> tuple[RenderedPage, ...]:
        site = site_variant.site
        now = datetime.now(UTC)
        posts_list: list[RenderedPage] = []
        for page in collection.pages:
            if page.draft:
                continue
            if page.date is not None and page.date > now:
                continue
            body = self._render_body(site, collection, page, context)
            social_image = self._write_social_card(
                site_variant,
                SocialCard(
                    site_title=site.title,
                    eyebrow=collection.title,
                    title=page.title,
                    description=site.description,
                    locale=site.locale,
                ),
                f"assets/social/{collection.output_slug}/{page.slug}.png",
            )
            readtime = None
            try:
                readtime = calculate_readtime_minutes(body)
            except Exception:
                readtime = None
            page_with_readtime = Page(
                slug=page.slug,
                title=page.title,
                source_path=page.source_path,
                original_source_path=page.original_source_path,
                date=page.date,
                authors=page.authors,
                draft=page.draft,
                pin=page.pin,
                readtime_minutes=readtime,
            )
            rendered_page = self._rendered_page(
                site_variant,
                site_variants,
                collection,
                page_with_readtime,
                body,
                social_image,
            )
            posts_list.append(rendered_page)
        posts_list.sort(
            key=lambda p: (
                0 if p.page.pin else 1,
                -p.page.date.timestamp() if p.page.date else 0,
                p.page.slug,
            )
        )
        return tuple(posts_list)

    def _write_assets(self, site_variant: SiteVariant) -> None:
        asset_path = site_variant.output_path / "assets"
        asset_path.mkdir(parents=True, exist_ok=True)
        for file_name, source in self._page_renderer.assets().items():
            (asset_path / file_name).write_text(source, encoding="utf-8")
        image = site_variant.site.image
        if image is None:
            return
        if image.name in self._page_renderer.assets():
            raise ValueError(
                f"Invalid site image {image}: basename collides with a "
                "packaged asset"
            )
        if not image.exists():
            raise FileNotFoundError(
                f"Missing site image {image}: expected existing image asset"
            )
        shutil.copy2(image, asset_path / image.name)

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
            navigation=site.navigation_for(
                None, None, collections=selected_collections
            ),
            language_links=index_language_links(site_variant, site_variants),
            version_links=version_links_for(
                site_variant, site_variant.output_path
            ),
            alternate_links=alternate_links_for(site_variants, ""),
            social_image=self._write_social_card(
                site_variant,
                SocialCard(
                    site_title=site.title,
                    eyebrow="",
                    title=site.title,
                    description=site.description,
                    locale=site.locale,
                ),
                "assets/social/index.png",
            ),
        )
        index_path = site_variant.output_path / "index.html"
        index_path.write_text(
            self._page_renderer.render_index(rendered_index), encoding="utf-8"
        )
        LOGGER.info(
            "site_index_rendered",
            extra={"context": {"output_path": str(index_path)}},
        )

    def _write_sitemap(
        self,
        site_variant: SiteVariant,
        selected_collections: tuple[ContentCollection, ...],
    ) -> None:
        site = site_variant.site
        if not site.url:
            return

        sitemap_path = site_variant.output_path / "sitemap.xml"
        sitemap_path.write_text(
            self._page_renderer.render_sitemap(site, selected_collections),
            encoding="utf-8",
        )

    def _write_robots_txt(self, site_variant: SiteVariant) -> None:
        robots_path = site_variant.output_path / "robots.txt"
        robots_path.write_text(
            self._page_renderer.render_robots_txt(site_variant.site),
            encoding="utf-8",
        )

    def _write_not_found(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        selected_collections: tuple[ContentCollection, ...],
    ) -> None:
        site = site_variant.site
        rendered_not_found = RenderedNotFound(
            site=site,
            navigation=absolute_navigation(
                site.navigation_for(
                    None, None, collections=selected_collections
                ),
                site,
            ),
            language_links=not_found_language_links(
                site_variant, site_variants
            ),
            version_links=not_found_version_links(site_variant),
            alternate_links=alternate_links_for(site_variants, "404.html"),
        )
        not_found_path = site_variant.output_path / "404.html"
        not_found_path.write_text(
            self._page_renderer.render_not_found(rendered_not_found),
            encoding="utf-8",
        )

    def _write_service_worker(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
    ) -> None:
        # Last in the variant build: the disk walk must see every emitted
        # file (pages, index, search index, sitemap, 404, assets). Only
        # variants nested *inside* this root are another worker's tree —
        # the outer root would otherwise swallow this variant's own files.
        output_path = site_variant.output_path
        nested_output_paths = tuple(
            variant.output_path
            for variant in site_variants
            if variant.output_path != output_path
            and variant.output_path.is_relative_to(output_path)
        )
        manifest = precache_manifest(output_path, nested_output_paths)
        (output_path / "sw.js").write_text(
            self._page_renderer.render_service_worker(manifest),
            encoding="utf-8",
        )

    def _write_social_card(
        self,
        site_variant: SiteVariant,
        card: SocialCard,
        relative_path: str,
    ) -> str | None:
        """Render one card into the variant tree; return its root-relative
        path for the head meta tags, or None when no plugin is installed."""
        renderer = self._social_card_renderer
        if renderer is None:
            return None
        card_path = site_variant.output_path / relative_path
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_bytes(renderer.render_social_card(card))
        return relative_path

    def _rendered_page(
        self,
        site_variant: SiteVariant,
        site_variants: tuple[SiteVariant, ...],
        collection: ContentCollection,
        page: Page,
        body: str,
        social_image: str | None,
    ) -> RenderedPage:
        site = site_variant.site
        previous_page = collection.previous_page(page)
        next_page = collection.next_page(page)
        # Generated intermediates (localized sources) carry no history —
        # revision facts always resolve against the authored file.
        revision_source = page.original_source_path or page.source_path
        return RenderedPage(
            site=site,
            collection=collection,
            page=page,
            article=self._article_outline_builder.build(
                page.title,
                body,
                site.extension_setting(
                    "i18n",
                    "label_heading_permalink",
                    "Permalink to this section",
                ),
            ),
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
            language_links=page_language_links(
                site_variant, site_variants, collection, page
            ),
            version_links=version_links_for(
                site_variant,
                site_variant.output_path / collection.output_slug,
            ),
            alternate_links=alternate_links_for(
                site_variants,
                f"{collection.output_slug}/{page.file_name()}",
            ),
            edit_url=self._edit_url(site, revision_source),
            last_updated=self._last_updated(site, revision_source),
            social_image=social_image,
            authors=page.authors,
            readtime_minutes=page.readtime_minutes,
        )

    def _edit_url(self, site: Site, source_path: Path) -> str | None:
        provider = self._source_revision_provider
        if not site.edit_base_url or provider is None:
            return None
        repository_path = provider.repository_path(source_path)
        if repository_path is None:
            return None
        return f"{site.edit_base_url.rstrip('/')}/{repository_path}"

    def _last_updated(self, site: Site, source_path: Path) -> date | None:
        provider = self._source_revision_provider
        if not site.last_updated or provider is None:
            return None
        return provider.newest_commit_date(source_path)

    def _pager_link(self, page: Page, relation: str) -> PagerLink:
        return PagerLink(
            label=page.title, href=page.file_name(), relation=relation
        )

    def _render_body(
        self,
        site: Site,
        collection: ContentCollection,
        page: Page,
        context: BuildContext,
    ) -> str:
        for renderer in self._content_renderers:
            if renderer.can_render(page.source_path):
                return self._process_rendered_html(
                    renderer.render(collection, page, context), site
                )

        raise ValueError(
            f"Unsupported page source {page.source_path}: expected renderer for suffix "
            f"{page.source_path.suffix}",
        )

    def _process_rendered_html(self, rendered_html: str, site: Site) -> str:
        processed_html = rendered_html
        for post_processor in self._html_post_processors:
            processed_html = post_processor.process(processed_html, site)

        return processed_html
