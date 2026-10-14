from importlib.resources import files
from pathlib import Path

from ssg.domain import (
    Article,
    ArticleHeading,
    ContentCollection,
    LanguageLink,
    Page,
    RenderedIndex,
    RenderedNotFound,
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


def test_render_page_emits_canonical_og_and_favicon(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path, url=True)
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
        '<link rel="canonical" '
        'href="https://example.com/docs/sample-collection/overview.html">'
        in rendered_html
    )
    assert (
        '<link rel="icon" href="../assets/favicon.svg" '
        'type="image/svg+xml">' in rendered_html
    )
    assert '<meta property="og:type" content="article">' in rendered_html
    assert (
        '<meta property="og:url" '
        'content="https://example.com/docs/sample-collection/overview.html">'
        in rendered_html
    )
    assert '<meta property="og:locale" content="en">' in rendered_html
    assert (
        '<meta property="og:description" '
        'content="Rendered content collections.">' in rendered_html
    )
    assert (
        '<meta property="og:site_name" content="Learning Site">'
        in rendered_html
    )


def test_render_index_emits_root_canonical_and_website_og(
    tmp_path: Path,
) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, collection, _page = _site_with_collection(tmp_path, url=True)
    rendered_index = RenderedIndex(
        site=site,
        collections=(collection,),
        navigation=site.navigation_for(None, None),
    )

    # Act
    rendered_html = renderer.render_index(rendered_index)

    # Assert
    assert (
        '<link rel="canonical" href="https://example.com/docs/">'
        in rendered_html
    )
    assert '<meta property="og:type" content="website">' in rendered_html
    assert (
        '<meta property="og:url" content="https://example.com/docs/">'
        in rendered_html
    )
    assert (
        '<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">'
        in rendered_html
    )


def test_render_page_omits_canonical_and_og_url_without_site_url(
    tmp_path: Path,
) -> None:
    # Arrange — no deployment URL configured: canonical and og:url have no
    # absolute base to resolve against, so they are skipped while the
    # remaining head metadata still renders.
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
    assert 'rel="canonical"' not in rendered_html
    assert 'property="og:url"' not in rendered_html
    assert '<meta property="og:title"' in rendered_html
    assert 'rel="icon"' in rendered_html


def test_render_page_prefixes_canonical_with_non_default_locale(
    tmp_path: Path,
) -> None:
    # Arrange — a pt-BR variant deploys under <site.url>/pt-BR/, so its
    # canonical must carry the locale prefix rather than collapse onto the
    # default-locale URL.
    renderer = JinjaPageRenderer()
    site, collection, page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        url="https://example.com/docs",
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
    assert (
        'href="https://example.com/docs/pt-BR/'
        'sample-collection/overview.html"' in rendered_html
    )
    assert '<meta property="og:locale" content="pt-BR">' in rendered_html


def test_assets_include_favicon() -> None:
    # Arrange / Act
    assets = JinjaPageRenderer().assets()

    # Assert
    assert "<svg" in assets["favicon.svg"]


def test_render_sitemap_lists_canonical_page_urls(tmp_path: Path) -> None:
    # Arrange — loc values must equal the canonical URLs head.html emits:
    # the locale root for index, <output_slug>/<slug>.html per page.
    renderer = JinjaPageRenderer()
    site, collection, _page = _site_with_collection(tmp_path, url=True)

    # Act
    sitemap_xml = renderer.render_sitemap(site, (collection,))

    # Assert
    assert sitemap_xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in sitemap_xml
    assert "<loc>https://example.com/docs/</loc>" in sitemap_xml
    assert (
        "<loc>https://example.com/docs/sample-collection/overview.html</loc>"
        in sitemap_xml
    )
    assert (
        "<loc>https://example.com/docs/sample-collection/details.html</loc>"
        in sitemap_xml
    )


def test_render_sitemap_prefixes_non_default_locale(tmp_path: Path) -> None:
    # Arrange — a pt-BR variant deploys under <site.url>/pt-BR/, so its
    # sitemap locs carry the locale prefix like its canonicals do.
    renderer = JinjaPageRenderer()
    site, collection, _page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
        url="https://example.com/docs",
    )

    # Act
    sitemap_xml = renderer.render_sitemap(localized_site, (collection,))

    # Assert
    assert "<loc>https://example.com/docs/pt-BR/</loc>" in sitemap_xml
    assert (
        "<loc>https://example.com/docs/pt-BR/"
        "sample-collection/overview.html</loc>" in sitemap_xml
    )


def test_render_sitemap_escapes_url_ampersands(tmp_path: Path) -> None:
    # Arrange — loc text must be XML-escaped (mkdocs passes each url
    # through |e); a bare & would produce a malformed document.
    renderer = JinjaPageRenderer()
    site, collection, _page = _site_with_collection(tmp_path)
    site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        url="https://example.com/docs?x=1&y=2",
    )

    # Act
    sitemap_xml = renderer.render_sitemap(site, (collection,))

    # Assert
    assert "x=1&amp;y=2" in sitemap_xml
    assert "x=1&y=2" not in sitemap_xml


def test_render_robots_txt_allows_all_and_points_at_sitemap(
    tmp_path: Path,
) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path, url=True)

    # Act
    robots_txt = renderer.render_robots_txt(site)

    # Assert
    assert "User-agent: *" in robots_txt
    assert "Allow: /" in robots_txt
    assert "Sitemap: https://example.com/docs/sitemap.xml" in robots_txt


def test_render_robots_txt_points_at_locale_sitemap_for_variant(
    tmp_path: Path,
) -> None:
    # Arrange — each locale root carries its own sitemap.xml, so the
    # variant's robots.txt points inside its locale prefix.
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
        url="https://example.com/docs",
    )

    # Act
    robots_txt = renderer.render_robots_txt(localized_site)

    # Assert
    assert "Sitemap: https://example.com/docs/pt-BR/sitemap.xml" in robots_txt


def test_render_robots_txt_omits_sitemap_line_without_site_url(
    tmp_path: Path,
) -> None:
    # Arrange — no deployment URL means no sitemap.xml is emitted, so the
    # Sitemap pointer would be a dead link.
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path)

    # Act
    robots_txt = renderer.render_robots_txt(site)

    # Assert
    assert "User-agent: *" in robots_txt
    assert "Allow: /" in robots_txt
    assert "Sitemap:" not in robots_txt


def test_render_not_found_keeps_site_chrome(tmp_path: Path) -> None:
    # Arrange — the 404 page is a shell page: same head/header/sidebar/footer
    # chrome as index.html (mkdocs extends its base template; starlight's
    # built-in route renders the common page).
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path)
    rendered_not_found = RenderedNotFound(
        site=site,
        navigation=site.navigation_for(None, None),
        language_links=(),
    )

    # Act
    rendered_html = renderer.render_not_found(rendered_not_found)

    # Assert
    assert '<header class="site-header">' in rendered_html
    assert '<aside class="sidebar" id="site-navigation">' in rendered_html
    assert '<footer class="site-footer">' in rendered_html
    assert (
        '<main class="content" id="main-content" tabindex="-1">'
        in rendered_html
    )
    assert '<section class="not-found' in rendered_html
    assert "404" in rendered_html
    assert "Page not found" in rendered_html
    assert "<title>404 - Learning Site</title>" in rendered_html


def test_render_not_found_absolutizes_assets_when_site_url_set(
    tmp_path: Path,
) -> None:
    # Arrange — a 404 may be served at any missing-path depth, where relative
    # asset hrefs would resolve under the missing directory; the template
    # prefixes assets/links with the absolute locale root (starlight emits
    # site-absolute URLs; mkdocs' relative 404 shares this limitation).
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path, url=True)
    rendered_not_found = RenderedNotFound(
        site=site,
        navigation=site.navigation_for(None, None),
        language_links=(),
    )

    # Act
    rendered_html = renderer.render_not_found(rendered_not_found)

    # Assert
    assert 'href="https://example.com/docs/assets/site.css"' in rendered_html
    assert (
        'content="https://example.com/docs/search-index.json"' in rendered_html
    )
    assert (
        'href="https://example.com/docs/assets/favicon.svg"' in rendered_html
    )
    assert 'src="https://example.com/docs/assets/site.js"' in rendered_html


def test_render_not_found_prefixes_assets_per_locale(
    tmp_path: Path,
) -> None:
    # Arrange — each locale root carries its own assets/, so a pt-BR 404
    # resolves them under the locale prefix like its canonical does.
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
        url="https://example.com/docs",
    )
    rendered_not_found = RenderedNotFound(
        site=localized_site,
        navigation=localized_site.navigation_for(None, None),
        language_links=(),
    )

    # Act
    rendered_html = renderer.render_not_found(rendered_not_found)

    # Assert
    assert '<html lang="pt-BR">' in rendered_html
    assert (
        'href="https://example.com/docs/pt-BR/assets/site.css"'
        in rendered_html
    )
    assert 'href="https://example.com/docs/pt-BR/404.html"' in rendered_html


def test_render_not_found_falls_back_to_relative_assets_without_site_url(
    tmp_path: Path,
) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path)
    rendered_not_found = RenderedNotFound(
        site=site,
        navigation=site.navigation_for(None, None),
        language_links=(),
    )

    # Act
    rendered_html = renderer.render_not_found(rendered_not_found)

    # Assert
    assert 'href="assets/site.css"' in rendered_html
    assert 'content="search-index.json"' in rendered_html


def test_render_not_found_uses_i18n_labels(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path)
    localized_site = Site(
        title=site.title,
        description=site.description,
        collections=site.collections,
        locale="pt-BR",
        extensions={
            "i18n": {
                "label_not_found": "Página não encontrada",
                "label_home": "Voltar ao início",
            }
        },
    )
    rendered_not_found = RenderedNotFound(
        site=localized_site,
        navigation=localized_site.navigation_for(None, None),
        language_links=(),
    )

    # Act
    rendered_html = renderer.render_not_found(rendered_not_found)

    # Assert
    assert "Página não encontrada" in rendered_html
    assert "Voltar ao início" in rendered_html
    assert "Page not found" not in rendered_html


def test_render_not_found_links_back_home(tmp_path: Path) -> None:
    # Arrange — starlight's 404 carries a "Go to home" action; ours points at
    # the navigation's home href (already locale-aware and absolutized by the
    # builder when site.url is set).
    renderer = JinjaPageRenderer()
    site, _collection, _page = _site_with_collection(tmp_path, url=True)
    rendered_not_found = RenderedNotFound(
        site=site,
        navigation=site.navigation_for(None, None),
        language_links=(),
    )

    # Act
    rendered_html = renderer.render_not_found(rendered_not_found)

    # Assert
    assert 'href="index.html"' in rendered_html
    assert "Back to home" in rendered_html


def _site_with_collection(
    tmp_path: Path, url: bool = False
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
        url="https://example.com/docs" if url else "",
    )
    return site, collection, page
