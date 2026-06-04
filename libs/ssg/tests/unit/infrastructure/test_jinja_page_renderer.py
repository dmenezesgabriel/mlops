from pathlib import Path

from ssg.domain.site import Article, ContentCollection, Page, RenderedIndex, RenderedPage, Site
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer


def test_render_page_includes_semantic_accessible_landmarks(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(title="Overview", body="<p>Rendered content.</p>"),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert '<a class="skip-link" href="#main-content">Skip to content</a>' in rendered_html
    assert '<nav aria-label="Primary">' in rendered_html
    assert '<main class="content" id="main-content" tabindex="-1">' in rendered_html
    assert '<article class="article" data-page-slug="overview">' in rendered_html
    assert 'aria-current="page"' in rendered_html
    assert "<p>Rendered content.</p>" in rendered_html


def test_render_index_lists_collections_as_content_cards(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, _page = _site_with_collection(tmp_path)
    rendered_index = RenderedIndex(
        site=site,
        collections=(collection,),
        navigation=site.navigation_for(None, None),
    )

    # Act
    rendered_html = renderer.render_index(rendered_index)

    # Assert
    assert '<section class="hero" aria-labelledby="site-heading">' in rendered_html
    collection_grid = '<section class="collection-grid" aria-labelledby="collections-heading">'
    assert collection_grid in rendered_html
    assert 'href="sample-collection/overview.html"' in rendered_html
    assert "Sample Collection" in rendered_html


def test_assets_include_stylesheet_and_menu_script() -> None:
    # Arrange / Act
    assets = JinjaPageRenderer().assets()

    # Assert
    assert "site.css" in assets
    assert "site.js" in assets
    assert "aria-expanded" in assets["site.js"]


def _site_with_collection(tmp_path: Path) -> tuple[Site, ContentCollection, Page]:
    page = Page(slug="overview", title="Overview", source_path=tmp_path / "README.md")
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
    )
    return site, collection, page
