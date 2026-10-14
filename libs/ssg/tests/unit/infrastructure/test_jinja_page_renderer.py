from importlib.resources import files
from pathlib import Path

from ssg.domain import (
    Article,
    ArticleHeading,
    ContentCollection,
    LanguageLink,
    Page,
    RenderedIndex,
    RenderedPage,
    Site,
)
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer


def test_render_page_includes_semantic_accessible_landmarks(
    tmp_path: Path,
) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview",
            body='<h2 id="problem-framing">Problem Framing</h2><p>Rendered content.</p>',
            headings=(
                ArticleHeading(
                    label="Problem Framing", href="#problem-framing", level=2
                ),
            ),
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert (
        '<a class="skip-link" href="#main-content">Skip to content</a>'
        in rendered_html
    )
    assert '<nav aria-label="Primary">' in rendered_html
    assert (
        '<main class="content" id="main-content" tabindex="-1">'
        in rendered_html
    )
    assert (
        '<article class="article" data-page-slug="overview">' in rendered_html
    )
    assert (
        '<aside class="article-toc" aria-label="On this page">'
        in rendered_html
    )
    toc_link = '<a class="article-toc__link--level-2" href="#problem-framing">Problem Framing</a>'
    assert toc_link in rendered_html
    assert "<body>" in rendered_html
    assert 'aria-current="page"' in rendered_html
    assert "<p>Rendered content.</p>" in rendered_html


def test_render_index_lists_collections_as_content_cards(
    tmp_path: Path,
) -> None:
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
    assert (
        '<section class="hero story-step" aria-labelledby="site-heading">'
        in rendered_html
    )
    collection_grid = '<section class="collection-grid" aria-labelledby="collections-heading">'
    assert collection_grid in rendered_html
    assert 'href="sample-collection/overview.html"' in rendered_html
    assert "Sample Collection" in rendered_html
    sidebar_html = rendered_html.split("</aside>", 1)[0]
    assert (
        '<a href="sample-collection/details.html">Details</a>'
        not in sidebar_html
    )


def test_render_page_omits_empty_table_of_contents(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview", body="<p>Rendered content.</p>", headings=()
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert "article-toc" not in rendered_html


def test_render_page_uses_site_locale_as_html_language(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
    )
    rendered_page = RenderedPage(
        site=localized_site,
        collection=collection,
        page=page,
        article=Article(
            title="Visao Geral", body="<p>Conteudo.</p>", headings=()
        ),
        navigation=localized_site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert '<html lang="pt-BR">' in rendered_html


def test_render_index_uses_site_locale_as_html_language(
    tmp_path: Path,
) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, _page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
    )
    rendered_index = RenderedIndex(
        site=localized_site,
        collections=(collection,),
        navigation=localized_site.navigation_for(None, None),
    )

    # Act
    rendered_html = renderer.render_index(rendered_index)

    # Assert
    assert '<html lang="pt-BR">' in rendered_html


def test_render_page_includes_language_switcher(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview", body="<p>Rendered content.</p>", headings=()
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
        language_links=(
            LanguageLink(label="en", href="overview.html", current=True),
            LanguageLink(
                label="pt-BR", href="../pt-BR/sample-collection/overview.html"
            ),
        ),
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert '<details class="language-switcher">' in rendered_html
    assert (
        '<span class="language-switcher__current">en</span>' in rendered_html
    )
    assert 'href="../pt-BR/sample-collection/overview.html"' in rendered_html


def test_assets_include_stylesheet_and_menu_script() -> None:
    # Arrange / Act
    assets = JinjaPageRenderer().assets()

    # Assert
    assert "site.css" in assets
    assert "site.js" in assets
    assert "aria-expanded" in assets["site.js"]
    assert "Newsreader" in assets["site.css"]
    assert "IntersectionObserver" in assets["site.js"]


def test_site_css_defines_dark_theme_variant() -> None:
    # Arrange / Act
    assets = JinjaPageRenderer().assets()

    # Assert
    site_css = assets["site.css"]
    assert "color-scheme: light dark" in site_css
    assert "light-dark(" in site_css
    assert 'body[data-theme="dark"]' in site_css
    assert 'body[data-theme="light"]' in site_css


def test_render_page_declares_color_scheme_meta(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview", body="<p>Rendered content.</p>", headings=()
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert '<meta name="color-scheme" content="light dark">' in rendered_html


def test_render_page_includes_theme_select_and_fouc_guard(
    tmp_path: Path,
) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview", body="<p>Rendered content.</p>", headings=()
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert 'class="theme-select"' in rendered_html
    assert 'aria-label="Theme"' in rendered_html
    assert '<option value="auto">Auto</option>' in rendered_html
    assert '<option value="light">Light</option>' in rendered_html
    assert '<option value="dark">Dark</option>' in rendered_html
    # The guard restores a stored pick ahead of first paint, so it must sit
    # before the first rendered element in <body>.
    assert rendered_html.index("localStorage.getItem('ssg-theme')") < (
        rendered_html.index("skip-link")
    )
    assert 'data-theme="editorial-lab"' not in rendered_html


def test_render_page_includes_search_ui(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview", body="<p>Rendered content.</p>", headings=()
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert '<div class="site-search" role="search">' in rendered_html
    assert 'class="search-input"' in rendered_html
    assert 'type="search"' in rendered_html
    assert 'aria-label="Search"' in rendered_html
    assert 'placeholder="Search pages"' in rendered_html
    assert 'aria-controls="search-results"' in rendered_html
    assert 'class="search-results"' in rendered_html
    assert 'role="listbox"' in rendered_html
    assert "No results found" in rendered_html


def test_render_page_search_index_meta_is_page_relative(
    tmp_path: Path,
) -> None:
    # Arrange — a page sits one level under the locale root, so the meta
    # carries the same ../ prefix as the site.css/site.js asset links.
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=Article(
            title="Overview", body="<p>Rendered content.</p>", headings=()
        ),
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert (
        '<meta name="ssg:search-index" content="../search-index.json">'
        in rendered_html
    )


def test_render_index_search_index_meta_is_root_relative(
    tmp_path: Path,
) -> None:
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
    assert (
        '<meta name="ssg:search-index" content="search-index.json">'
        in rendered_html
    )


def test_render_page_localizes_search_labels(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
        extensions={
            "i18n": {
                "label_search": "Busca",
                "label_search_placeholder": "Buscar páginas",
                "label_search_no_results": "Nenhum resultado encontrado",
            }
        },
    )
    rendered_page = RenderedPage(
        site=localized_site,
        collection=collection,
        page=page,
        article=Article(
            title="Visao Geral", body="<p>Conteudo.</p>", headings=()
        ),
        navigation=localized_site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert 'aria-label="Busca"' in rendered_html
    assert 'placeholder="Buscar páginas"' in rendered_html
    assert "Nenhum resultado encontrado" in rendered_html


def test_assets_include_search_wiring() -> None:
    # Arrange / Act
    assets = JinjaPageRenderer().assets()

    # Assert
    assert "has-search" in assets["site.js"]
    assert "ssg:search-index" in assets["site.js"]
    assert ".site-search" in assets["site.css"]
    assert ".search-results" in assets["site.css"]


def test_render_page_localizes_theme_select_labels(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
        extensions={
            "i18n": {
                "label_theme": "Tema",
                "label_theme_auto": "Automático",
                "label_theme_light": "Claro",
                "label_theme_dark": "Escuro",
            }
        },
    )
    rendered_page = RenderedPage(
        site=localized_site,
        collection=collection,
        page=page,
        article=Article(
            title="Visao Geral", body="<p>Conteudo.</p>", headings=()
        ),
        navigation=localized_site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )

    # Act
    rendered_html = renderer.render_page(rendered_page)

    # Assert
    assert 'aria-label="Tema"' in rendered_html
    assert '<option value="auto">Automático</option>' in rendered_html
    assert '<option value="light">Claro</option>' in rendered_html
    assert '<option value="dark">Escuro</option>' in rendered_html


def test_assets_include_theme_select_wiring() -> None:
    # Arrange / Act
    assets = JinjaPageRenderer().assets()

    # Assert
    assert "ssg-theme" in assets["site.js"]
    assert "has-theme-select" in assets["site.js"]
    assert ".theme-select" in assets["site.css"]


def test_frontend_templates_and_static_assets_are_package_files() -> None:
    # Arrange
    frontend_files = files("ssg.infrastructure.frontend")

    # Act
    template_path = frontend_files.joinpath("templates", "page.html")
    style_path = frontend_files.joinpath("static", "css", "site.css")
    script_path = frontend_files.joinpath("static", "js", "site.js")

    # Assert
    assert template_path.is_file()
    assert style_path.is_file()
    assert script_path.is_file()
    assert "{% extends 'base.html' %}" in template_path.read_text(
        encoding="utf-8"
    )
    assert "Newsreader" in style_path.read_text(encoding="utf-8")
    assert "IntersectionObserver" in script_path.read_text(encoding="utf-8")


def _site_with_collection(
    tmp_path: Path,
) -> tuple[Site, ContentCollection, Page]:
    page = Page(
        slug="overview", title="Overview", source_path=tmp_path / "README.md"
    )
    details = Page(
        slug="details", title="Details", source_path=tmp_path / "details.md"
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(page, details),
        videos={},
    )
    site = Site(
        title="Learning Site",
        description="Rendered content collections.",
        collections=(collection,),
    )
    return site, collection, page
