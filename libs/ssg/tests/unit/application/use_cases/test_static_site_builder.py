import json
from datetime import date
from pathlib import Path

import pytest
from ssg.application.use_cases.static_site_builder import StaticSiteBuilder
from ssg.domain import (
    Article,
    ArticleHeading,
    BuildContext,
    ContentCollection,
    Page,
    PrecacheManifest,
    RenderedIndex,
    RenderedNotFound,
    RenderedPage,
    Site,
    SiteVariant,
    SocialCard,
)
from ssg.infrastructure.in_memory_dependency_tracker import (
    InMemoryDependencyTracker,
)
from ssg.infrastructure.in_memory_search_index import InMemorySearchIndex
from ssg.infrastructure.single_site_variant_provider import (
    SingleSiteVariantProvider,
)


class SpySiteRepository:
    def __init__(self, site: Site) -> None:
        self.site = site
        self.load_calls: list[Path] = []

    def load(self, config_path: Path) -> Site:
        self.load_calls.append(config_path)
        return self.site


class SpyContentRenderer:
    def __init__(self) -> None:
        self.render_calls: list[
            tuple[ContentCollection, Page, BuildContext]
        ] = []

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".md"

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str:
        self.render_calls.append((collection, page, context))
        return "<p>Rendered body</p>"


class SpyPageRenderer:
    def __init__(self) -> None:
        self.render_page_calls: list[RenderedPage] = []
        self.render_index_calls: list[RenderedIndex] = []
        self.render_sitemap_calls: list[
            tuple[Site, tuple[ContentCollection, ...]]
        ] = []
        self.render_robots_txt_calls: list[Site] = []
        self.render_not_found_calls: list[RenderedNotFound] = []
        self.render_service_worker_calls: list[PrecacheManifest] = []

    def render_page(self, rendered_page: RenderedPage) -> str:
        self.render_page_calls.append(rendered_page)
        return f"<html>{rendered_page.article.body}</html>"

    def render_index(self, rendered_index: RenderedIndex) -> str:
        self.render_index_calls.append(rendered_index)
        return "<html>Index</html>"

    def render_sitemap(
        self, site: Site, collections: tuple[ContentCollection, ...]
    ) -> str:
        self.render_sitemap_calls.append((site, collections))
        return "<sitemap/>"

    def render_robots_txt(self, site: Site) -> str:
        self.render_robots_txt_calls.append(site)
        return "robots"

    def render_not_found(self, rendered_not_found: RenderedNotFound) -> str:
        self.render_not_found_calls.append(rendered_not_found)
        return "<html>404</html>"

    def render_service_worker(self, manifest: PrecacheManifest) -> str:
        self.render_service_worker_calls.append(manifest)
        return "// sw"

    def assets(self) -> dict[str, str]:
        return {"site.css": "body {}", "site.js": ""}


class SpyArticleOutlineBuilder:
    def __init__(self) -> None:
        self.build_calls: list[tuple[str, str, str]] = []

    def build(self, title: str, body: str, permalink_label: str) -> Article:
        self.build_calls.append((title, body, permalink_label))
        return Article(
            title=title,
            body='<h2 id="overview">Overview</h2>',
            headings=(
                ArticleHeading(
                    label="Overview",
                    href="#overview",
                    level=2,
                    section_text="Section text",
                ),
            ),
            plain_text="Plain text",
        )


class SpySocialCardRenderer:
    """Captures the card VOs it was asked to paint; returns marked bytes."""

    def __init__(self) -> None:
        self.render_calls: list[SocialCard] = []

    def render_social_card(self, card: SocialCard) -> bytes:
        self.render_calls.append(card)
        return f"png:{card.locale}:{card.title}".encode()


class SpyHtmlPostProcessor:
    def __init__(self) -> None:
        self.process_calls: list[tuple[str, Site]] = []

    def process(self, rendered_html: str, site: Site) -> str:
        self.process_calls.append((rendered_html, site))
        return rendered_html.replace("Rendered body", "Processed body")


class DependencyRecordingRenderer:
    """Registers a configurable dependency set per render so tests can
    change a page's dependencies between builds."""

    def __init__(self, dependency_paths: tuple[Path, ...]) -> None:
        self.dependency_paths = dependency_paths

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".md"

    def render(
        self, collection: ContentCollection, page: Page, context: BuildContext
    ) -> str:
        if context.dependency_tracker is not None:
            context.dependency_tracker.register_dependency(
                page, page.source_path
            )
            for dependency_path in self.dependency_paths:
                context.dependency_tracker.register_dependency(
                    page, dependency_path
                )
        return "<p>Rendered body</p>"


class LocalizedSiteVariantProvider:
    def variants(
        self, site: Site, context: BuildContext
    ) -> tuple[SiteVariant, ...]:
        localized_site = Site(
            title="Site em Portugues",
            description=site.description,
            collections=site.collections,
            locale="pt-BR",
            default_locale=site.default_locale,
            extensions=site.extensions,
            url=site.url,
            image=site.image,
        )
        return (
            SiteVariant(site=site, output_path=context.output_path),
            SiteVariant(
                site=localized_site, output_path=context.output_path / "pt-BR"
            ),
        )


class FakeSourceRevisionProvider:
    """Fixed revision facts; records the paths it was asked about."""

    def __init__(
        self, commit_date: date | None, repository_path: str | None
    ) -> None:
        self._commit_date = commit_date
        self._repository_path = repository_path
        self.commit_date_calls: list[Path] = []
        self.repository_path_calls: list[Path] = []

    def newest_commit_date(self, path: Path) -> date | None:
        self.commit_date_calls.append(path)
        return self._commit_date

    def repository_path(self, path: Path) -> str | None:
        self.repository_path_calls.append(path)
        return self._repository_path


class TestStaticSiteBuilder:
    def test_build_delegates_to_repository_content_renderer_and_page_renderer(
        self,
        tmp_path: Path,
    ) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        site_repository = SpySiteRepository(site)
        content_renderer = SpyContentRenderer()
        page_renderer = SpyPageRenderer()
        article_outline_builder = SpyArticleOutlineBuilder()
        builder = StaticSiteBuilder(
            site_repository=site_repository,
            content_renderers=(content_renderer,),
            page_renderer=page_renderer,
            article_outline_builder=article_outline_builder,
            site_variant_provider=SingleSiteVariantProvider(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(config_path, output_path)

        # Assert
        collection_output_path = output_path / "sample-collection"
        rendered_page = page_renderer.render_page_calls[0]
        assert site_repository.load_calls == [config_path]
        assert len(content_renderer.render_calls) == 1
        call_collection, call_page, call_context = (
            content_renderer.render_calls[0]
        )
        assert (call_collection, call_page) == (collection, page)
        assert call_context.output_path == output_path
        assert page_renderer.render_index_calls[0].collections == (collection,)
        assert (rendered_page.collection, rendered_page.page) == (
            collection,
            page,
        )
        assert article_outline_builder.build_calls == [
            ("Overview", "<p>Rendered body</p>", "Permalink to this section")
        ]
        assert (
            rendered_page.article.body,
            rendered_page.article.has_table_of_contents(),
        ) == (
            '<h2 id="overview">Overview</h2>',
            True,
        )
        assert (
            (output_path / "index.html").read_text(encoding="utf-8"),
            (output_path / "assets" / "site.css").read_text(encoding="utf-8"),
            (collection_output_path / "overview.html").read_text(
                encoding="utf-8"
            ),
        ) == (
            "<html>Index</html>",
            "body {}",
            '<html><h2 id="overview">Overview</h2></html>',
        )

    def test_build_applies_html_post_processors_before_article_outline(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        article_outline_builder = SpyArticleOutlineBuilder()
        html_post_processor = SpyHtmlPostProcessor()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=article_outline_builder,
            html_post_processors=(html_post_processor,),
            site_variant_provider=SingleSiteVariantProvider(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert html_post_processor.process_calls == [
            ("<p>Rendered body</p>", site)
        ]
        assert article_outline_builder.build_calls == [
            ("Overview", "<p>Processed body</p>", "Permalink to this section")
        ]

    def test_build_rejects_unsupported_page_source(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.rst",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act / Assert

        with pytest.raises(ValueError, match="Unsupported page source"):
            builder.build(tmp_path / "site.yaml", tmp_path / "build")

    def test_build_writes_each_site_variant_to_its_output_path(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        page_renderer = SpyPageRenderer()
        content_renderer = SpyContentRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(content_renderer,),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert (tmp_path / "build" / "index.html").exists()
        assert (
            tmp_path / "build" / "sample-collection" / "overview.html"
        ).exists()
        assert (tmp_path / "build" / "pt-BR" / "index.html").exists()
        assert (
            tmp_path
            / "build"
            / "pt-BR"
            / "sample-collection"
            / "overview.html"
        ).exists()
        assert [
            call.site.locale for call in page_renderer.render_page_calls
        ] == ["en", "pt-BR"]
        assert len(content_renderer.render_calls) == 2
        assert (
            content_renderer.render_calls[0][2].output_path
            == tmp_path / "build"
        )
        assert (
            content_renderer.render_calls[1][2].output_path
            == tmp_path / "build" / "pt-BR"
        )

    def test_build_adds_relative_language_links_for_index_and_pages(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        english_index_links = page_renderer.render_index_calls[
            0
        ].language_links
        portuguese_index_links = page_renderer.render_index_calls[
            1
        ].language_links
        english_page_links = page_renderer.render_page_calls[0].language_links
        portuguese_page_links = page_renderer.render_page_calls[
            1
        ].language_links
        assert [
            (link.label, link.href, link.current)
            for link in english_index_links
        ] == [
            ("en", "index.html", True),
            ("pt-BR", "pt-BR/index.html", False),
        ]
        assert [
            (link.label, link.href, link.current)
            for link in portuguese_index_links
        ] == [
            ("en", "../index.html", False),
            ("pt-BR", "index.html", True),
        ]
        assert [
            (link.label, link.href, link.current)
            for link in english_page_links
        ] == [
            ("en", "overview.html", True),
            ("pt-BR", "../pt-BR/sample-collection/overview.html", False),
        ]
        assert [
            (link.label, link.href, link.current)
            for link in portuguese_page_links
        ] == [
            ("en", "../../sample-collection/overview.html", False),
            ("pt-BR", "overview.html", True),
        ]

    def test_build_adds_absolute_alternate_links_per_locale_and_x_default(
        self, tmp_path: Path
    ) -> None:
        # Arrange — hreflang hrefs must be absolute (they cross origins when
        # crawlers follow them), so they resolve through each variant's
        # absolute_url, unlike the relative header switcher links.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        index_links = page_renderer.render_index_calls[0].alternate_links
        page_links = page_renderer.render_page_calls[0].alternate_links
        not_found_links = page_renderer.render_not_found_calls[
            0
        ].alternate_links
        assert [(link.hreflang, link.href) for link in index_links] == [
            ("en", "https://example.com/docs/"),
            ("pt-BR", "https://example.com/docs/pt-BR/"),
            ("x-default", "https://example.com/docs/"),
        ]
        assert [(link.hreflang, link.href) for link in page_links] == [
            ("en", "https://example.com/docs/sample-collection/overview.html"),
            (
                "pt-BR",
                "https://example.com/docs/pt-BR/"
                "sample-collection/overview.html",
            ),
            (
                "x-default",
                "https://example.com/docs/sample-collection/overview.html",
            ),
        ]
        assert [(link.hreflang, link.href) for link in not_found_links] == [
            ("en", "https://example.com/docs/404.html"),
            ("pt-BR", "https://example.com/docs/pt-BR/404.html"),
            ("x-default", "https://example.com/docs/404.html"),
        ]

    def test_build_emits_no_alternate_links_without_site_url(
        self, tmp_path: Path
    ) -> None:
        # Arrange — multiple variants but no deployment URL: hreflang hrefs
        # require an absolute base, so nothing is emitted.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert page_renderer.render_index_calls[0].alternate_links == ()
        assert page_renderer.render_page_calls[0].alternate_links == ()
        assert page_renderer.render_not_found_calls[0].alternate_links == ()

    def test_build_emits_no_alternate_links_for_a_single_variant(
        self, tmp_path: Path
    ) -> None:
        # Arrange — a monolingual site has nothing to alternate to even with
        # a deployment URL configured.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert page_renderer.render_index_calls[0].alternate_links == ()
        assert page_renderer.render_page_calls[0].alternate_links == ()

    def test_build_copies_site_image_into_every_variant_assets(
        self, tmp_path: Path
    ) -> None:
        # Arrange — og:image/twitter:image resolve to
        # <variant>/assets/<image name>, so each locale root needs its own
        # copy of the configured file.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        image_path = tmp_path / "card.png"
        image_path.write_bytes(b"png bytes")
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
            image=image_path,
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )
        output_path = tmp_path / "build"

        # Act
        builder.build(tmp_path / "site.yaml", output_path)

        # Assert
        assert (output_path / "assets" / "card.png").read_bytes() == (
            b"png bytes"
        )
        assert (
            output_path / "pt-BR" / "assets" / "card.png"
        ).read_bytes() == b"png bytes"

    def test_build_raises_for_missing_site_image(self, tmp_path: Path) -> None:
        # Arrange — the image lands in every variant's assets, so a missing
        # file fails the build loudly instead of emitting a dead og:image.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        missing_image = tmp_path / "absent.png"
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            image=missing_image,
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act / Assert
        with pytest.raises(FileNotFoundError, match="absent.png"):
            builder.build(tmp_path / "site.yaml", tmp_path / "build")

    def test_build_rejects_site_image_shadowing_a_packaged_asset(
        self, tmp_path: Path
    ) -> None:
        # Arrange — the image copies into assets/ beside the packaged
        # site.css/site.js; a colliding basename would silently clobber them.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        image_path = tmp_path / "site.css"
        image_path.write_bytes(b"not css")
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            image=image_path,
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act / Assert
        with pytest.raises(ValueError, match="collides"):
            builder.build(tmp_path / "site.yaml", tmp_path / "build")

    def test_build_writes_social_card_per_page_and_index(
        self, tmp_path: Path
    ) -> None:
        # Arrange — per-page og:image cards emit under assets/social/ and
        # the rendered VOs carry the root-relative path for head.html.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="Rendered content collections.",
            collections=(collection,),
            url="https://example.com/docs",
        )
        card_renderer = SpySocialCardRenderer()
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            social_card_renderer=card_renderer,
        )
        output_path = tmp_path / "build"

        # Act
        builder.build(tmp_path / "site.yaml", output_path)

        # Assert
        assert card_renderer.render_calls == [
            SocialCard(
                site_title="Learning Site",
                eyebrow="",
                title="Learning Site",
                description="Rendered content collections.",
                locale="en",
            ),
            SocialCard(
                site_title="Learning Site",
                eyebrow="Sample Collection",
                title="Overview",
                description="Rendered content collections.",
                locale="en",
            ),
        ]
        assert (output_path / "assets/social/index.png").read_bytes() == (
            b"png:en:Learning Site"
        )
        assert (
            output_path / "assets/social/sample-collection/overview.png"
        ).read_bytes() == b"png:en:Overview"
        assert (
            page_renderer.render_index_calls[0].social_image
            == "assets/social/index.png"
        )
        assert (
            page_renderer.render_page_calls[0].social_image
            == "assets/social/sample-collection/overview.png"
        )
        assert page_renderer.render_not_found_calls[0].social_image is None

    def test_build_writes_social_cards_per_variant_locale(
        self, tmp_path: Path
    ) -> None:
        # Arrange — cards carry the variant's own titles and land under each
        # locale root so <variant>/assets/social/… resolves per locale.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
        )
        card_renderer = SpySocialCardRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            social_card_renderer=card_renderer,
        )
        output_path = tmp_path / "build"

        # Act
        builder.build(tmp_path / "site.yaml", output_path)

        # Assert
        assert [card.locale for card in card_renderer.render_calls] == [
            "en",
            "en",
            "pt-BR",
            "pt-BR",
        ]
        assert card_renderer.render_calls[2].site_title == (
            "Site em Portugues"
        )
        assert (
            output_path / "pt-BR/assets/social/sample-collection/overview.png"
        ).read_bytes() == b"png:pt-BR:Overview"

    def test_build_without_social_card_renderer_emits_no_cards(
        self, tmp_path: Path
    ) -> None:
        # Arrange — the plugin is optional: without it the build stays
        # byte-identical to pre-card output and pages fall back to
        # site.image for og:image.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )
        output_path = tmp_path / "build"

        # Act
        builder.build(tmp_path / "site.yaml", output_path)

        # Assert
        assert not (output_path / "assets/social").exists()
        assert page_renderer.render_index_calls[0].social_image is None
        assert page_renderer.render_page_calls[0].social_image is None

    def test_incremental_build_skips_cards_for_unaffected_pages(
        self, tmp_path: Path
    ) -> None:
        # Arrange — a skipped page keeps its already-emitted card: the path
        # is deterministic, so only the rebuilt page's card re-renders.
        config_path = tmp_path / "site.yaml"
        output_path = tmp_path / "build"
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1, page2),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))
        dependency_tracker = InMemoryDependencyTracker()
        card_renderer = SpySocialCardRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=dependency_tracker,
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
            social_card_renderer=card_renderer,
        )
        builder.build(config_path, output_path)
        card_renderer.render_calls.clear()
        # A full build clears the tracker; register page2's dependency so
        # the incremental run treats it as affected and page1 as skipped.
        dependency_tracker.register_dependency(page2, page2.source_path)

        # Act
        builder.build(
            config_path, output_path, changed_paths={page2.source_path}
        )

        # Assert — index re-renders (it is always rewritten); only the
        # affected page's card regenerates, page1's file stays on disk.
        assert [card.title for card in card_renderer.render_calls] == [
            "Site",
            "Page 2",
        ]
        assert (output_path / "assets/social/sample/page1.png").exists()
        assert (
            output_path / "assets/social/sample/page2.png"
        ).read_bytes() == b"png:en:Page 2"

    def test_build_scopes_index_navigation_to_selected_collection(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        first = ContentCollection(
            name="coll_a",
            title="Coll A",
            source_root=tmp_path,
            output_slug="coll-a",
            pages=(
                Page(
                    slug="overview",
                    title="Overview",
                    source_path=tmp_path / "a.md",
                ),
            ),
            videos={},
        )
        second = ContentCollection(
            name="coll_b",
            title="Coll B",
            source_root=tmp_path,
            output_slug="coll-b",
            pages=(
                Page(
                    slug="overview",
                    title="Overview",
                    source_path=tmp_path / "b.md",
                ),
            ),
            videos={},
        )
        site = Site(title="Site", description="", collections=(first, second))
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            site_variant_provider=SingleSiteVariantProvider(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(config_path, output_path, collection_name="coll_a")

        # Assert
        navigation = page_renderer.render_index_calls[0].navigation
        assert [section.title for section in navigation.sections] == ["Coll A"]
        assert [section.href for section in navigation.sections] == [
            "coll-a/overview.html"
        ]
        assert not (output_path / "coll-b").exists()

    def test_build_skips_unaffected_pages_during_incremental_build(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1, page2),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))

        dependency_tracker = InMemoryDependencyTracker()
        dependency_tracker.register_dependency(page2, page2.source_path)

        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=dependency_tracker,
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )

        # Act
        builder.build(
            config_path, output_path, changed_paths={page2.source_path}
        )

        # Assert
        assert len(page_renderer.render_page_calls) == 1
        assert page_renderer.render_page_calls[0].page == page2

    def test_build_rebuilds_all_when_site_yaml_changes(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1,),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))

        dependency_tracker = InMemoryDependencyTracker()
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            dependency_tracker=dependency_tracker,
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
        )

        # Act
        builder.build(config_path, output_path, changed_paths={config_path})

        # Assert
        assert len(page_renderer.render_page_calls) == 1
        assert page_renderer.render_page_calls[0].page == page1

    def test_incremental_rebuild_replaces_rendered_pages_dependency_set(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        config_path = tmp_path / "site.yaml"
        output_path = tmp_path / "build"
        page = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page,),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))
        dependency_tracker = InMemoryDependencyTracker()
        content_renderer = DependencyRecordingRenderer(
            dependency_paths=(tmp_path / "dep_a.md",)
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(content_renderer,),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=dependency_tracker,
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )
        builder.build(config_path, output_path)
        content_renderer.dependency_paths = (tmp_path / "dep_b.md",)

        # Act
        builder.build(
            config_path, output_path, changed_paths={page.source_path}
        )

        # Assert — a dependency dropped by the re-rendered page must stop
        # invalidating it; keeping it means a stale Page object and a dead
        # key are pinned in the persistent tracker.
        assert (
            dependency_tracker.affected_pages({tmp_path / "dep_a.md"}) == set()
        )
        assert dependency_tracker.affected_pages({tmp_path / "dep_b.md"}) == {
            page
        }

    def test_rebuilds_keep_dependency_key_counts_flat(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        config_path = tmp_path / "site.yaml"
        output_path = tmp_path / "build"
        page = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page,),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))
        dependency_tracker = InMemoryDependencyTracker()
        content_renderer = DependencyRecordingRenderer(dependency_paths=())
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(content_renderer,),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=dependency_tracker,
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )
        builder.build(config_path, output_path)

        # Act — each rebuild swaps in a never-seen dependency path, the
        # growth vector G-53 measured (dead keys pin a stale Page member).
        for index in range(4):
            content_renderer.dependency_paths = (tmp_path / f"dep_{index}.md",)
            builder.build(
                config_path, output_path, changed_paths={page.source_path}
            )

        # Assert — only the live dep set remains: the page's own source
        # plus the current extra path.
        assert len(dependency_tracker.dependencies) == 2
        assert (
            sum(
                len(pages)
                for pages in dependency_tracker.dependencies.values()
            )
            == 2
        )

    def test_build_writes_search_index_per_site_variant(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert — one index file per variant output path: default locale
        # at the root, pt-BR under its own directory.
        expected_entries = [
            {
                "title": "Overview",
                "text": "Plain text",
                "location": "sample-collection/overview.html",
            },
            {
                "title": "Overview",
                "text": "Section text",
                "location": "sample-collection/overview.html#overview",
            },
        ]
        english_index = json.loads(
            (tmp_path / "build" / "search-index.json").read_text(
                encoding="utf-8"
            )
        )
        portuguese_index = json.loads(
            (tmp_path / "build" / "pt-BR" / "search-index.json").read_text(
                encoding="utf-8"
            )
        )
        assert english_index == {"docs": expected_entries}
        assert portuguese_index == {"docs": expected_entries}

    def test_incremental_build_keeps_skipped_pages_index_entries(
        self, tmp_path: Path
    ) -> None:
        # Arrange — incremental rebuilds skip unaffected pages; their search
        # entries must survive in the rewritten index.
        config_path = tmp_path / "site.yaml"
        output_path = tmp_path / "build"
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1, page2),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))
        content_renderer = DependencyRecordingRenderer(dependency_paths=())
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(content_renderer,),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )
        builder.build(config_path, output_path)

        # Act
        builder.build(
            config_path, output_path, changed_paths={page2.source_path}
        )

        # Assert
        index = json.loads(
            (output_path / "search-index.json").read_text(encoding="utf-8")
        )
        assert [entry["location"] for entry in index["docs"]] == [
            "sample/page1.html",
            "sample/page1.html#overview",
            "sample/page2.html",
            "sample/page2.html#overview",
        ]

    def test_full_rebuild_clears_stale_index_entries(
        self, tmp_path: Path
    ) -> None:
        # Arrange — a page dropped from the site config must leave the index:
        # the config-change rebuild path clears accumulated entries.
        config_path = tmp_path / "site.yaml"
        output_path = tmp_path / "build"
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1, page2),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))
        site_repository = SpySiteRepository(site)
        builder = StaticSiteBuilder(
            site_repository=site_repository,
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )
        builder.build(config_path, output_path)
        trimmed_collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1,),
            videos={},
        )
        site_repository.site = Site(
            title="Site", description="", collections=(trimmed_collection,)
        )

        # Act
        builder.build(config_path, output_path, changed_paths={config_path})

        # Assert
        index = json.loads(
            (output_path / "search-index.json").read_text(encoding="utf-8")
        )
        assert [entry["location"] for entry in index["docs"]] == [
            "sample/page1.html",
            "sample/page1.html#overview",
        ]

    def test_build_writes_sitemap_and_robots_per_site_variant(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert — each variant root gets both files, default locale at the
        # build root and pt-BR under its own directory.
        for variant_path in (tmp_path / "build", tmp_path / "build" / "pt-BR"):
            assert (variant_path / "sitemap.xml").read_text(
                encoding="utf-8"
            ) == "<sitemap/>"
            assert (variant_path / "robots.txt").read_text(
                encoding="utf-8"
            ) == "robots"
        assert [
            call_site.locale
            for call_site, _collections in page_renderer.render_sitemap_calls
        ] == ["en", "pt-BR"]
        assert [
            call_collections
            for _site, call_collections in page_renderer.render_sitemap_calls
        ] == [(collection,), (collection,)]
        assert [
            call_site.locale
            for call_site in page_renderer.render_robots_txt_calls
        ] == ["en", "pt-BR"]

    def test_build_writes_robots_but_skips_sitemap_without_site_url(
        self, tmp_path: Path
    ) -> None:
        # Arrange — sitemap <loc> entries must be absolute URLs; without a
        # configured deployment base there is nothing valid to emit, while
        # robots.txt is still useful (matching the head canonical gate).
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=SingleSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )
        output_path = tmp_path / "build"

        # Act
        builder.build(tmp_path / "site.yaml", output_path)

        # Assert
        assert not (output_path / "sitemap.xml").exists()
        assert page_renderer.render_sitemap_calls == []
        assert (output_path / "robots.txt").read_text(
            encoding="utf-8"
        ) == "robots"

    def test_incremental_build_sitemap_lists_skipped_pages(
        self, tmp_path: Path
    ) -> None:
        # Arrange — an incremental rebuild rewrites only affected pages, but
        # the skipped pages still exist in the output and must stay listed.
        config_path = tmp_path / "site.yaml"
        output_path = tmp_path / "build"
        page1 = Page(
            slug="page1", title="Page 1", source_path=tmp_path / "page1.md"
        )
        page2 = Page(
            slug="page2", title="Page 2", source_path=tmp_path / "page2.md"
        )
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1, page2),
            videos={},
        )
        site = Site(
            title="Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )
        builder.build(config_path, output_path)

        # Act
        builder.build(
            config_path, output_path, changed_paths={page2.source_path}
        )

        # Assert
        _site, collections = page_renderer.render_sitemap_calls[-1]
        assert collections == (collection,)
        assert collections[0].pages == (page1, page2)

    def test_build_writes_404_page_per_site_variant(
        self, tmp_path: Path
    ) -> None:
        # Arrange — hosts serve the root 404.html for any missing path, so
        # each locale root carries its own copy (mkdocs ships it as a theme
        # template; starlight emits a built-in route).
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        for variant_path in (tmp_path / "build", tmp_path / "build" / "pt-BR"):
            assert (variant_path / "404.html").read_text(
                encoding="utf-8"
            ) == "<html>404</html>"
        assert [
            call.site.locale for call in page_renderer.render_not_found_calls
        ] == ["en", "pt-BR"]

    def test_404_urls_are_absolute_when_site_url_set(
        self, tmp_path: Path
    ) -> None:
        # Arrange — a served 404 may sit at any missing-path depth (e.g.
        # GitHub Pages answers /mlops/a/b/c with the root 404.html), so
        # relative hrefs would resolve against the missing path's directory;
        # with site.url configured every on-page URL is emitted absolute.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            url="https://example.com/docs",
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        english, portuguese = page_renderer.render_not_found_calls
        assert (
            english.navigation.home_href
            == "https://example.com/docs/index.html"
        )
        assert english.navigation.sections[0].href == (
            "https://example.com/docs/sample-collection/overview.html"
        )
        assert [
            (link.label, link.href) for link in english.language_links
        ] == [
            ("en", "https://example.com/docs/404.html"),
            ("pt-BR", "https://example.com/docs/pt-BR/404.html"),
        ]
        assert (
            portuguese.navigation.home_href
            == "https://example.com/docs/pt-BR/index.html"
        )
        assert [
            link.href for link in portuguese.language_links if link.current
        ] == ["https://example.com/docs/pt-BR/404.html"]

    def test_build_populates_edit_link_and_last_updated(
        self, tmp_path: Path
    ) -> None:
        # Arrange — starlight shape: editLink.baseUrl + repo-relative source
        # path; lastUpdated = the source file's newest commit date.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            edit_base_url="https://github.com/example/repo/edit/main/",
            last_updated=True,
        )
        revisions = FakeSourceRevisionProvider(
            commit_date=date(2025, 1, 2),
            repository_path="content/sample_collection/README.md",
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
            source_revision_provider=revisions,
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        rendered_page = page_renderer.render_page_calls[0]
        assert rendered_page.edit_url == (
            "https://github.com/example/repo/edit/main/"
            "content/sample_collection/README.md"
        )
        assert rendered_page.last_updated == date(2025, 1, 2)
        assert revisions.repository_path_calls == [page.source_path]
        assert revisions.commit_date_calls == [page.source_path]

    def test_build_queries_original_source_path_when_set(
        self, tmp_path: Path
    ) -> None:
        # Arrange — localized variants render a generated intermediate file;
        # revision facts must come from the authored source it replaced.
        generated_source = tmp_path / ".ssg" / "generated" / "page.md"
        original_source = tmp_path / "content" / "page.md"
        page = Page(
            slug="overview",
            title="Overview",
            source_path=generated_source,
            original_source_path=original_source,
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            edit_base_url="https://github.com/example/repo/edit/main",
            last_updated=True,
        )
        revisions = FakeSourceRevisionProvider(
            commit_date=date(2025, 1, 2),
            repository_path="content/page.md",
        )
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
            source_revision_provider=revisions,
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert revisions.repository_path_calls == [original_source]
        assert revisions.commit_date_calls == [original_source]

    def test_build_omits_page_meta_when_features_not_configured(
        self, tmp_path: Path
    ) -> None:
        # Arrange — both features are opt-in: no edit_base_url, no
        # last_updated flag means the provider is never probed.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site", description="", collections=(collection,)
        )
        revisions = FakeSourceRevisionProvider(
            commit_date=date(2025, 1, 2), repository_path="README.md"
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
            source_revision_provider=revisions,
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        rendered_page = page_renderer.render_page_calls[0]
        assert rendered_page.edit_url is None
        assert rendered_page.last_updated is None
        assert revisions.repository_path_calls == []
        assert revisions.commit_date_calls == []

    def test_build_omits_page_meta_when_revisions_unavailable(
        self, tmp_path: Path
    ) -> None:
        # Arrange — configured but git has nothing to say (file outside any
        # work tree): the meta row degrades away instead of failing.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            edit_base_url="https://github.com/example/repo/edit/main",
            last_updated=True,
        )
        revisions = FakeSourceRevisionProvider(
            commit_date=None, repository_path=None
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
            source_revision_provider=revisions,
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        rendered_page = page_renderer.render_page_calls[0]
        assert rendered_page.edit_url is None
        assert rendered_page.last_updated is None

    def test_build_omits_page_meta_without_revision_provider(
        self, tmp_path: Path
    ) -> None:
        # Arrange — a builder composed without the port (e.g. minimal test
        # harnesses) renders the page with no meta rather than failing.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
            edit_base_url="https://github.com/example/repo/edit/main",
            last_updated=True,
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
            site_variant_provider=SingleSiteVariantProvider(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        rendered_page = page_renderer.render_page_calls[0]
        assert rendered_page.edit_url is None
        assert rendered_page.last_updated is None

    def test_404_urls_stay_relative_without_site_url(
        self, tmp_path: Path
    ) -> None:
        # Arrange — no deployment URL means there is no absolute base to
        # resolve against; the page keeps relative hrefs (mkdocs' shape) and
        # renders correctly when served at its own root path.
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        english, portuguese = page_renderer.render_not_found_calls
        assert english.navigation.home_href == "index.html"
        assert english.navigation.sections[0].href == (
            "sample-collection/overview.html"
        )
        assert [link.href for link in english.language_links] == [
            "404.html",
            "pt-BR/404.html",
        ]
        assert [link.href for link in portuguese.language_links] == [
            "../404.html",
            "404.html",
        ]

    def test_build_writes_a_service_worker_per_variant_root(
        self, tmp_path: Path
    ) -> None:
        # Arrange — offline precaching is per locale: each variant root
        # ships its own sw.js so its scope covers only its own tree (the
        # pt-BR output nests inside the default root).
        page = Page(
            slug="overview",
            title="Overview",
            source_path=tmp_path / "README.md",
        )
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(
            title="Learning Site",
            description="",
            collections=(collection,),
        )
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=InMemoryDependencyTracker(),
            search_index=InMemorySearchIndex(),
        )
        output_path = tmp_path / "build"

        # Act
        builder.build(tmp_path / "site.yaml", output_path)

        # Assert
        english, portuguese = page_renderer.render_service_worker_calls
        assert (output_path / "sw.js").read_text(encoding="utf-8") == "// sw"
        assert (output_path / "pt-BR" / "sw.js").read_text(
            encoding="utf-8"
        ) == "// sw"
        assert "sample-collection/overview.html" in english.urls
        assert "index.html" in english.urls
        assert "404.html" in english.urls
        assert not any(url.startswith("pt-BR/") for url in english.urls)
        assert "sample-collection/overview.html" in portuguese.urls
