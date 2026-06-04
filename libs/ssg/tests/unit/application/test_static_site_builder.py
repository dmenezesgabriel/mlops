from pathlib import Path

import pytest
from ssg.application.static_site_builder import StaticSiteBuilder
from ssg.domain.site import ContentCollection, Page, RenderedIndex, RenderedPage, Site


class SpySiteRepository:
    def __init__(self, site: Site) -> None:
        self.site = site
        self.load_calls: list[Path] = []

    def load(self, config_path: Path) -> Site:
        self.load_calls.append(config_path)
        return self.site


class SpyContentRenderer:
    def __init__(self) -> None:
        self.render_calls: list[tuple[ContentCollection, Page, Path]] = []

    def can_render(self, source_path: Path) -> bool:
        return source_path.suffix == ".md"

    def render(self, collection: ContentCollection, page: Page, output_path: Path) -> str:
        self.render_calls.append((collection, page, output_path))
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


def test_build_delegates_to_repository_content_renderer_and_page_renderer(
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
    builder = StaticSiteBuilder(
        site_repository=site_repository,
        content_renderers=(content_renderer,),
        page_renderer=page_renderer,
    )

    # Act
    builder.build(config_path, output_path)

    # Assert
    collection_output_path = output_path / "sample-collection"
    assert site_repository.load_calls == [config_path]
    assert content_renderer.render_calls == [(collection, page, collection_output_path)]
    assert page_renderer.render_index_calls[0].collections == (collection,)
    assert page_renderer.render_page_calls[0].collection == collection
    assert page_renderer.render_page_calls[0].page == page
    assert page_renderer.render_page_calls[0].article.body == "<p>Rendered body</p>"
    assert (output_path / "index.html").read_text(encoding="utf-8") == "<html>Index</html>"
    assert (output_path / "assets" / "site.css").read_text(encoding="utf-8") == "body {}"
    assert (collection_output_path / "overview.html").read_text(encoding="utf-8") == (
        "<html><p>Rendered body</p></html>"
    )


def test_build_rejects_unsupported_page_source(tmp_path: Path) -> None:
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
