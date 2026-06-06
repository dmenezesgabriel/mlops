from pathlib import Path

import pytest
from ssg.application.static_site_builder import StaticSiteBuilder
from ssg.domain.site import (
    Article,
    ArticleHeading,
    BuildContext,
    ContentCollection,
    Page,
    RenderedIndex,
    RenderedPage,
    Site,
    SiteVariant,
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
        self.render_calls: list[tuple[ContentCollection, Page, BuildContext]] = []

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".md"

    def render(self, collection: ContentCollection, page: Page, context: BuildContext) -> str:
        self.render_calls.append((collection, page, context))
        return "<p>Rendered body</p>"


class SpyPageRenderer:
    def __init__(self) -> None:
        self.render_page_calls: list[RenderedPage] = []
        self.render_index_calls: list[RenderedIndex] = []

    def render_page(self, rendered_page: RenderedPage) -> str:
        self.render_page_calls.append(rendered_page)
        return f"<html>{rendered_page.article.body}</html>"

    def render_index(self, rendered_index: RenderedIndex) -> str:
        self.render_index_calls.append(rendered_index)
        return "<html>Index</html>"

    def assets(self) -> dict[str, str]:
        return {"site.css": "body {}", "site.js": ""}


class SpyArticleOutlineBuilder:
    def __init__(self) -> None:
        self.build_calls: list[tuple[str, str]] = []

    def build(self, title: str, body: str) -> Article:
        self.build_calls.append((title, body))
        return Article(
            title=title,
            body='<h2 id="overview">Overview</h2>',
            headings=(ArticleHeading(label="Overview", href="#overview", level=2),),
        )


class SpyHtmlPostProcessor:
    def __init__(self) -> None:
        self.process_calls: list[tuple[str, Site]] = []

    def process(self, rendered_html: str, site: Site) -> str:
        self.process_calls.append((rendered_html, site))
        return rendered_html.replace("Rendered body", "Processed body")


class LocalizedSiteVariantProvider:
    def variants(self, site: Site, context: BuildContext) -> tuple[SiteVariant, ...]:
        localized_site = Site(
            title="Site em Portugues",
            description=site.description,
            collections=site.collections,
            locale="pt-BR",
            default_locale=site.default_locale,
            extensions=site.extensions,
        )
        return (
            SiteVariant(site=site, output_path=context.output_path),
            SiteVariant(site=localized_site, output_path=context.output_path / "pt-BR"),
        )


class TestStaticSiteBuilder:
    def test_build_delegates_to_repository_content_renderer_and_page_renderer(
        self,
        tmp_path: Path,
    ) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        page = Page(slug="overview", title="Overview", source_path=tmp_path / "README.md")
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(title="Learning Site", description="", collections=(collection,))
        site_repository = SpySiteRepository(site)
        content_renderer = SpyContentRenderer()
        page_renderer = SpyPageRenderer()
        article_outline_builder = SpyArticleOutlineBuilder()
        builder = StaticSiteBuilder(
            site_repository=site_repository,
            content_renderers=(content_renderer,),
            page_renderer=page_renderer,
            article_outline_builder=article_outline_builder,
        )

        # Act
        builder.build(config_path, output_path)

        # Assert
        collection_output_path = output_path / "sample-collection"
        rendered_page = page_renderer.render_page_calls[0]
        assert site_repository.load_calls == [config_path]
        assert len(content_renderer.render_calls) == 1
        call_collection, call_page, call_context = content_renderer.render_calls[0]
        assert (call_collection, call_page) == (collection, page)
        assert call_context.output_path == output_path
        assert page_renderer.render_index_calls[0].collections == (collection,)
        assert (rendered_page.collection, rendered_page.page) == (collection, page)
        assert article_outline_builder.build_calls == [("Overview", "<p>Rendered body</p>")]
        assert (rendered_page.article.body, rendered_page.article.has_table_of_contents()) == (
            '<h2 id="overview">Overview</h2>',
            True,
        )
        assert (
            (output_path / "index.html").read_text(encoding="utf-8"),
            (output_path / "assets" / "site.css").read_text(encoding="utf-8"),
            (collection_output_path / "overview.html").read_text(encoding="utf-8"),
        ) == (
            "<html>Index</html>",
            "body {}",
            '<html><h2 id="overview">Overview</h2></html>',
        )

    def test_build_applies_html_post_processors_before_article_outline(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        page = Page(slug="overview", title="Overview", source_path=tmp_path / "README.md")
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(title="Learning Site", description="", collections=(collection,))
        article_outline_builder = SpyArticleOutlineBuilder()
        html_post_processor = SpyHtmlPostProcessor()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
            article_outline_builder=article_outline_builder,
            html_post_processors=(html_post_processor,),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert html_post_processor.process_calls == [("<p>Rendered body</p>", site)]
        assert article_outline_builder.build_calls == [("Overview", "<p>Processed body</p>")]

    def test_build_rejects_unsupported_page_source(self, tmp_path: Path) -> None:
        # Arrange
        page = Page(slug="overview", title="Overview", source_path=tmp_path / "README.rst")
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(title="Learning Site", description="", collections=(collection,))
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=SpyPageRenderer(),
        )

        # Act / Assert

        with pytest.raises(ValueError, match="Unsupported page source"):
            builder.build(tmp_path / "site.yaml", tmp_path / "build")

    def test_build_writes_each_site_variant_to_its_output_path(self, tmp_path: Path) -> None:
        # Arrange
        page = Page(slug="overview", title="Overview", source_path=tmp_path / "README.md")
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(title="Learning Site", description="", collections=(collection,))
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        assert (tmp_path / "build" / "index.html").exists()
        assert (tmp_path / "build" / "sample-collection" / "overview.html").exists()
        assert (tmp_path / "build" / "pt-BR" / "index.html").exists()
        assert (tmp_path / "build" / "pt-BR" / "sample-collection" / "overview.html").exists()
        assert [call.site.locale for call in page_renderer.render_page_calls] == ["en", "pt-BR"]

    def test_build_adds_relative_language_links_for_index_and_pages(self, tmp_path: Path) -> None:
        # Arrange
        page = Page(slug="overview", title="Overview", source_path=tmp_path / "README.md")
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample-collection",
            pages=(page,),
            videos={},
        )
        site = Site(title="Learning Site", description="", collections=(collection,))
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            site_variant_provider=LocalizedSiteVariantProvider(),
        )

        # Act
        builder.build(tmp_path / "site.yaml", tmp_path / "build")

        # Assert
        english_index_links = page_renderer.render_index_calls[0].language_links
        portuguese_index_links = page_renderer.render_index_calls[1].language_links
        english_page_links = page_renderer.render_page_calls[0].language_links
        portuguese_page_links = page_renderer.render_page_calls[1].language_links
        assert [(link.label, link.href, link.current) for link in english_index_links] == [
            ("en", "index.html", True),
            ("pt-BR", "pt-BR/index.html", False),
        ]
        assert [(link.label, link.href, link.current) for link in portuguese_index_links] == [
            ("en", "../index.html", False),
            ("pt-BR", "index.html", True),
        ]
        assert [(link.label, link.href, link.current) for link in english_page_links] == [
            ("en", "overview.html", True),
            ("pt-BR", "../pt-BR/sample-collection/overview.html", False),
        ]
        assert [(link.label, link.href, link.current) for link in portuguese_page_links] == [
            ("en", "../../sample-collection/overview.html", False),
            ("pt-BR", "overview.html", True),
        ]

    def test_build_skips_unaffected_pages_during_incremental_build(self, tmp_path: Path) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        page1 = Page(slug="page1", title="Page 1", source_path=tmp_path / "page1.md")
        page2 = Page(slug="page2", title="Page 2", source_path=tmp_path / "page2.md")
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1, page2),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))

        from ssg.application.dependency_tracker import InMemoryDependencyTracker

        dependency_tracker = InMemoryDependencyTracker()
        dependency_tracker.register_dependency(page2, page2.source_path)

        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            article_outline_builder=SpyArticleOutlineBuilder(),
            dependency_tracker=dependency_tracker,
        )

        # Act
        builder.build(config_path, output_path, changed_paths={page2.source_path})

        # Assert
        assert len(page_renderer.render_page_calls) == 1
        assert page_renderer.render_page_calls[0].page == page2

    def test_build_rebuilds_all_when_site_yaml_changes(self, tmp_path: Path) -> None:
        # Arrange
        config_path = tmp_path / "site" / "site.yaml"
        output_path = tmp_path / "site" / "build"
        page1 = Page(slug="page1", title="Page 1", source_path=tmp_path / "page1.md")
        collection = ContentCollection(
            name="sample",
            title="Sample",
            source_root=tmp_path,
            output_slug="sample",
            pages=(page1,),
            videos={},
        )
        site = Site(title="Site", description="", collections=(collection,))

        from ssg.application.dependency_tracker import InMemoryDependencyTracker

        dependency_tracker = InMemoryDependencyTracker()
        page_renderer = SpyPageRenderer()
        builder = StaticSiteBuilder(
            site_repository=SpySiteRepository(site),
            content_renderers=(SpyContentRenderer(),),
            page_renderer=page_renderer,
            dependency_tracker=dependency_tracker,
        )

        # Act
        builder.build(config_path, output_path, changed_paths={config_path})

        # Assert
        assert len(page_renderer.render_page_calls) == 1
        assert page_renderer.render_page_calls[0].page == page1
