import re
from pathlib import Path
from urllib.parse import urldefrag

import pytest
from playwright.sync_api import Locator, Page, expect


@pytest.mark.playwright
class TestBuiltSiteSmoke:
    def test_built_site_supports_navigation_i18n_and_mobile_menu(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_home_page(page, built_site_url)
        _assert_language_switcher(page, built_site_url)
        _assert_configured_pages(page, built_site_url)
        _assert_notebook_and_code_pages(page, built_site_url)
        _assert_static_assets(page, built_site_url)
        _assert_alert_callouts(page, built_site_url)
        _assert_mobile_menu(page, built_site_url)
        _assert_code_copy_buttons(page, built_site_url)
        _assert_code_copy_degrades_without_js(page, built_site_url)

    def test_built_site_honors_dark_color_scheme(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_dark_scheme_default(page, built_site_url)
        _assert_light_scheme_default(page, built_site_url)
        _assert_data_theme_overrides_media(page, built_site_url)
        _assert_dark_scheme_without_js(page, built_site_url)

    def test_built_site_theme_toggle_persists(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_theme_select_flips(page, built_site_url)
        _assert_theme_persists_across_reload(page, built_site_url)
        _assert_theme_auto_follows_system(page, built_site_url)
        _assert_theme_select_i18n(page, built_site_url)
        _assert_theme_select_hidden_without_js(page, built_site_url)

    def test_built_site_search_filters_and_ranks(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_search_fetches_lazily(page, built_site_url)
        _assert_search_ranks_title_hits_first(page, built_site_url)
        _assert_search_keyboard_and_no_results(page, built_site_url)
        _assert_search_scopes_to_locale(page, built_site_url)
        _assert_search_hidden_without_js(page, built_site_url)

    def test_built_site_toc_scrollspy_and_back_to_top(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_toc_scrollspy_marks_current_section(page, built_site_url)
        _assert_back_to_top_shows_on_scroll_up(page, built_site_url)
        _assert_back_to_top_localizes(page, built_site_url)
        _assert_back_to_top_hidden_without_js(page, built_site_url)

    def test_built_site_mobile_toc_disclosure(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_mobile_toc_disclosure(page, built_site_url)
        _assert_mobile_toc_link_pick_closes(page, built_site_url)
        _assert_mobile_toc_closes_on_escape_and_outside_click(
            page, built_site_url
        )
        _assert_mobile_toc_localizes(page, built_site_url)
        _assert_mobile_toc_hidden_on_desktop(page, built_site_url)
        _assert_mobile_toc_works_without_js(page, built_site_url)

    def test_built_site_shows_page_meta(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        _assert_page_meta_english(page, built_site_url)
        _assert_page_meta_pt_br(page, built_site_url)
        _assert_page_meta_sits_above_pager(page, built_site_url)
        _assert_page_meta_visible_without_js(page, built_site_url)


def _assert_home_page(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    # Read the configured site title so tests remain in sync with site config
    import yaml

    site_config_path = Path("site/site.yaml")
    if not site_config_path.exists():
        site_config_path = Path("../../site/site.yaml")
    site_config = yaml.safe_load(site_config_path.read_text())
    expected_title = site_config.get("site", {}).get("title", "")
    expect(page.locator("h1")).to_contain_text(expected_title)
    expect(page.locator(".site-header")).to_be_visible()
    expect(page.locator("#site-navigation")).to_be_visible()
    expect(page.locator(".collection-card")).to_contain_text(
        "NYC Taxi Demand Forecasting"
    )
    expect(page.locator("link[href='assets/site.css']")).to_have_count(1)
    expect(page.locator("script[src='assets/site.js']")).to_have_count(1)


def _assert_language_switcher(page: Page, base_url: str) -> None:
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/overview.html",
        wait_until="networkidle",
    )
    page.locator(".language-switcher summary").click()
    expect(page.locator(".language-switcher a[href*='pt-BR']")).to_be_visible()
    page.locator(".language-switcher a[href*='pt-BR']").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("html")).to_have_attribute("lang", "pt-BR")
    expect(page.locator(".language-switcher__current")).to_contain_text(
        "pt-BR"
    )


def _assert_configured_pages(page: Page, base_url: str) -> None:
    checked_links: set[str] = set()
    for path in _configured_paths():
        page.goto(f"{base_url}{path}", wait_until="networkidle")
        _assert_page_chrome(page, path)
        _assert_internal_links(page, base_url, path, checked_links)


def _assert_page_chrome(page: Page, path: str) -> None:
    body_text = page.locator("body").inner_text()
    assert "{{" not in body_text, path
    assert "}}" not in body_text, path
    assert "SSG_TRANSCLUSION" not in body_text, path
    assert "StrictUndefined" not in body_text, path
    expect(page.locator(".site-header")).to_be_visible()
    expect(page.locator("#site-navigation")).to_be_visible()

    if "overview.html" in path:
        # Assert: verify that the embedded MLOps diagram is visible
        expect(
            page.locator(
                "figure.image-frame img[src='assets/images/mlops_lifecycle.png']"
            )
        ).to_be_visible()


def _assert_internal_links(
    page: Page,
    base_url: str,
    path: str,
    checked_links: set[str],
) -> None:
    hrefs = page.locator("a[href]").evaluate_all(
        "links => links.map(link => link.href)"
    )
    for href in hrefs:
        if not isinstance(href, str) or not href.startswith(base_url):
            continue

        link_without_fragment = urldefrag(href).url
        if link_without_fragment in checked_links:
            continue

        checked_links.add(link_without_fragment)
        response = page.request.get(link_without_fragment)
        assert response.status < 400, (
            f"{path} links to {link_without_fragment}"
        )


def _assert_notebook_and_code_pages(page: Page, base_url: str) -> None:
    notebook_path = "/nyc-taxi-demand-forecasting/feature-engineering.html"
    page.goto(f"{base_url}{notebook_path}", wait_until="networkidle")
    expect(page.locator(".notebook-cell").first).to_be_visible()
    # Notebook rendering uses `.notebook-input` for code cells in the current
    # renderer; assert its visibility rather than the deprecated `.source-panel`.
    expect(page.locator(".notebook-input").first).to_be_visible()
    expect(page.locator(".highlight-token").first).to_be_visible()

    code_path = "/nyc-taxi-demand-forecasting/model-evaluation.html"
    page.goto(f"{base_url}{code_path}", wait_until="networkidle")
    expect(page.locator(".highlight-token").first).to_be_visible()
    expect(page.locator(".article-toc")).to_be_visible()


def _assert_static_assets(page: Page, base_url: str) -> None:
    css_response = page.request.get(f"{base_url}/assets/site.css")
    script_response = page.request.get(f"{base_url}/assets/site.js")
    assert css_response.status == 200
    assert script_response.status == 200
    assert "Newsreader" in css_response.text()
    assert "IntersectionObserver" in script_response.text()


def _assert_alert_callouts(page: Page, base_url: str) -> None:
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/data-collection.html",
        wait_until="networkidle",
    )
    alert = page.locator(".markdown-alert.markdown-alert-note")
    expect(alert).to_be_visible()
    expect(alert.locator(".markdown-alert-icon")).to_be_visible()
    expect(alert.locator(".markdown-alert-title")).to_contain_text("Note")

    page.goto(
        f"{base_url}/pt-BR/nyc-taxi-demand-forecasting/data-collection.html",
        wait_until="networkidle",
    )
    expect(
        page.locator(".markdown-alert .markdown-alert-title")
    ).to_contain_text("Nota")


def _assert_mobile_menu(page: Page, base_url: str) -> None:
    page.set_viewport_size({"width": 390, "height": 820})
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/problem-framing.html",
        wait_until="networkidle",
    )
    expect(page.locator(".menu-toggle")).to_be_visible()
    expect(page.locator("#site-navigation")).not_to_be_visible()
    page.locator(".menu-toggle").click()
    expect(page.locator(".menu-toggle")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(page.locator("#site-navigation")).to_be_visible()


def _assert_code_copy_buttons(page: Page, base_url: str) -> None:
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/model-evaluation.html",
        wait_until="networkidle",
    )
    # Every fenced block on the page carries the button (FR-15)
    assert page.locator(".article-body .code-frame").count() > 0
    assert (
        page.locator(".article-body pre").count()
        == page.locator(".article-body .code-frame pre").count()
    )

    first_button = page.locator(".code-copy-button").first
    expected_text = page.locator(".code-frame pre > code").first.evaluate(
        "code => code.textContent.trimEnd()"
    )
    first_button.click()
    expect(first_button).to_contain_text("Copied!")
    assert page.evaluate("navigator.clipboard.readText()") == expected_text


def _assert_code_copy_degrades_without_js(page: Page, base_url: str) -> None:
    # The button renders only under the `has-code-copy` class that site.js
    # adds when the clipboard API exists; blocking the script must leave no
    # dead button in the page.
    page.route("**/assets/site.js", lambda route: route.abort())
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/model-evaluation.html",
        wait_until="networkidle",
    )
    page.unroute("**/assets/site.js")
    expect(page.locator(".code-copy-button").first).not_to_be_visible()


# Computed body (background-color, color) per scheme; source of truth is the
# :root palette in site.css (`light-dark()` pairs).
_LIGHT_BODY = ("rgb(243, 234, 216)", "rgb(21, 17, 13)")
_DARK_BODY = ("rgb(27, 21, 16)", "rgb(241, 231, 212)")


def _body_colors(page: Page) -> tuple[str, str]:
    background = page.evaluate(
        "() => getComputedStyle(document.body).backgroundColor"
    )
    color = page.evaluate("() => getComputedStyle(document.body).color")
    return str(background), str(color)


def _assert_dark_scheme_default(page: Page, base_url: str) -> None:
    page.emulate_media(color_scheme="dark")
    page.goto(f"{base_url}/", wait_until="networkidle")
    assert _body_colors(page) == _DARK_BODY
    page.goto(f"{base_url}/pt-BR/", wait_until="networkidle")
    assert _body_colors(page) == _DARK_BODY


def _assert_light_scheme_default(page: Page, base_url: str) -> None:
    page.emulate_media(color_scheme="light")
    page.goto(f"{base_url}/", wait_until="networkidle")
    assert _body_colors(page) == _LIGHT_BODY


def _assert_data_theme_overrides_media(page: Page, base_url: str) -> None:
    # data-theme is the explicit-choice contract: a script-written light/dark
    # value must beat the media query so the user's pick survives.
    page.emulate_media(color_scheme="dark")
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.evaluate("() => { document.body.dataset.theme = 'light'; }")
    assert _body_colors(page) == _LIGHT_BODY
    page.emulate_media(color_scheme="light")
    page.evaluate("() => { document.body.dataset.theme = 'dark'; }")
    assert _body_colors(page) == _DARK_BODY


def _assert_dark_scheme_without_js(page: Page, base_url: str) -> None:
    # site.js aborted: the palette still resolves dark at first paint, so a
    # no-JS reader gets the dark scheme with no light flash.
    page.route("**/assets/site.js", lambda route: route.abort())
    page.emulate_media(color_scheme="dark")
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.unroute("**/assets/site.js")
    assert _body_colors(page) == _DARK_BODY


def _assert_theme_select_flips(page: Page, base_url: str) -> None:
    page.emulate_media(color_scheme="light")
    page.goto(f"{base_url}/", wait_until="networkidle")
    theme_select = page.locator(".theme-select")
    expect(theme_select).to_be_visible()
    expect(theme_select).to_have_value("auto")
    theme_select.select_option("dark")
    # The explicit pick must beat the media query (still emulated light).
    expect(page.locator("body")).to_have_attribute("data-theme", "dark")
    assert _body_colors(page) == _DARK_BODY


def _assert_theme_persists_across_reload(page: Page, base_url: str) -> None:
    # The inline guard re-applies the stored pick before site.js runs, so
    # the select value is restored too once the wiring loads.
    page.reload(wait_until="networkidle")
    expect(page.locator("body")).to_have_attribute("data-theme", "dark")
    expect(page.locator(".theme-select")).to_have_value("dark")
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/overview.html",
        wait_until="networkidle",
    )
    expect(page.locator("body")).to_have_attribute("data-theme", "dark")


def _assert_theme_auto_follows_system(page: Page, base_url: str) -> None:
    # auto drops the override entirely; the stylesheet then tracks the
    # media query live with no JS involved.
    page.locator(".theme-select").select_option("auto")
    assert page.locator("body").get_attribute("data-theme") is None
    page.emulate_media(color_scheme="dark")
    assert _body_colors(page) == _DARK_BODY
    page.emulate_media(color_scheme="light")
    assert _body_colors(page) == _LIGHT_BODY


def _assert_theme_select_i18n(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/pt-BR/", wait_until="networkidle")
    theme_select = page.locator(".theme-select")
    expect(theme_select).to_have_attribute("aria-label", "Tema")
    expect(theme_select.locator('option[value="dark"]')).to_have_text("Escuro")


def _assert_theme_select_hidden_without_js(page: Page, base_url: str) -> None:
    # Without site.js the select would be a dead control; the
    # has-theme-select gate keeps it hidden.
    page.route("**/assets/site.js", lambda route: route.abort())
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.unroute("**/assets/site.js")
    expect(page.locator(".theme-select")).not_to_be_visible()


def _assert_search_fetches_lazily(page: Page, base_url: str) -> None:
    # The index is a per-page lazy fetch: it must not be requested until the
    # reader actually engages the input.
    index_requests: list[str] = []
    page.on(
        "request",
        lambda request: (
            index_requests.append(request.url)
            if "search-index.json" in request.url
            else None
        ),
    )
    page.goto(f"{base_url}/", wait_until="networkidle")
    assert index_requests == []

    page.locator(".search-input").click()
    page.locator(".search-input").fill("demand")
    expect(page.locator(".search-results")).to_be_visible()
    assert len(index_requests) == 1
    assert index_requests[0].endswith("/search-index.json")


def _assert_search_ranks_title_hits_first(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.locator(".search-input").fill("Monitoring")
    results = page.locator(".search-results li a")
    expect(results.first).to_be_visible()
    # The page titled "Monitoring" must outrank pages that only mention the
    # term in body text.
    expect(results.first).to_have_text("Monitoring")
    first_href = results.first.get_attribute("href")
    assert first_href is not None and "model-monitoring" in first_href

    results.first.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_contain_text("Monitoring")


def _assert_search_keyboard_and_no_results(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    search_input = page.locator(".search-input")
    search_input.fill("demand")
    expect(page.locator(".search-results")).to_be_visible()

    # ArrowDown hands focus to the first ranked link.
    page.keyboard.press("ArrowDown")
    focused = page.evaluate(
        "() => document.activeElement && document.activeElement.className"
    )
    assert "search-result-link" in str(focused)

    page.keyboard.press("Escape")
    expect(page.locator(".search-results")).not_to_be_visible()

    search_input.fill("zzzqqq")
    expect(page.locator(".search-results")).to_be_visible()
    expect(page.locator(".search-no-results")).to_be_visible()
    expect(page.locator(".search-no-results")).to_contain_text(
        "No results found"
    )


def _assert_search_scopes_to_locale(page: Page, base_url: str) -> None:
    # The pt-BR variant builds its own index; results must stay inside the
    # locale's URL prefix.
    page.goto(f"{base_url}/pt-BR/", wait_until="networkidle")
    page.locator(".search-input").fill("Monitoramento")
    results = page.locator(".search-results li a")
    expect(results.first).to_be_visible()
    hrefs = results.evaluate_all(
        "links => links.map(link => link.getAttribute('href'))"
    )
    assert hrefs, "expected ranked results under /pt-BR/"
    assert all("/pt-BR/" in str(href) for href in hrefs)


def _assert_search_hidden_without_js(page: Page, base_url: str) -> None:
    # Without site.js the input would be a dead control; the has-search gate
    # keeps the whole widget hidden.
    page.route("**/assets/site.js", lambda route: route.abort())
    page.goto(f"{base_url}/", wait_until="networkidle")
    page.unroute("**/assets/site.js")
    expect(page.locator(".site-search")).not_to_be_visible()


def _scroll_heading_into_pick_band(page: Page, href: str) -> None:
    # Land the target ~150px below the viewport top, inside the scrollspy's
    # pick band just under the sticky header. 'instant' bypasses the CSS
    # smooth-scroll so the scroll lands before the assertions poll.
    page.evaluate(
        """id => {
            const el = document.getElementById(id);
            window.scrollTo({
                top: el.getBoundingClientRect().top + window.scrollY - 150,
                behavior: 'instant',
            });
        }""",
        href.lstrip("#"),
    )


def _assert_toc_scrollspy_marks_current_section(
    page: Page, base_url: str
) -> None:
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/model-evaluation.html",
        wait_until="networkidle",
    )
    toc_links = page.locator(".article-toc a[href^='#']")
    first_href = toc_links.first.get_attribute("href")
    second_href = toc_links.nth(1).get_attribute("href")
    assert first_href and second_href

    _scroll_heading_into_pick_band(page, second_href)
    expect(toc_links.nth(1)).to_have_attribute("aria-current", "true")

    _scroll_heading_into_pick_band(page, first_href)
    expect(toc_links.first).to_have_attribute("aria-current", "true")
    expect(toc_links.nth(1)).not_to_have_attribute("aria-current", "true")


def _scroll_down_then_up(page: Page) -> None:
    # 'instant' scrolls: html { scroll-behavior: smooth } would otherwise
    # animate the jump and let the second call retarget a running
    # animation, leaving the last scroll direction nondeterministic.
    page.evaluate(
        "() => window.scrollTo({"
        "  top: document.documentElement.scrollHeight, behavior: 'instant'"
        "})"
    )
    # Scroll events dispatch asynchronously — let the down-scroll land so
    # site.js records the lower position before the upward jump registers
    # as "scrolling up".
    page.wait_for_function(
        "() => window.scrollY + window.innerHeight"
        "    >= document.documentElement.scrollHeight"
    )
    page.evaluate("() => window.scrollBy({ top: -400, behavior: 'instant' })")


def _assert_back_to_top_shows_on_scroll_up(page: Page, base_url: str) -> None:
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/model-evaluation.html",
        wait_until="networkidle",
    )
    button = page.locator(".back-to-top")
    expect(button).not_to_be_visible()

    _scroll_down_then_up(page)
    expect(button).to_be_visible()

    button.click()
    page.wait_for_function("() => window.scrollY === 0")
    expect(button).not_to_be_visible()


def _assert_back_to_top_localizes(page: Page, base_url: str) -> None:
    page.goto(
        f"{base_url}/pt-BR/nyc-taxi-demand-forecasting/model-evaluation.html",
        wait_until="networkidle",
    )
    expect(page.locator(".back-to-top")).to_have_text("Voltar ao topo")


def _assert_back_to_top_hidden_without_js(page: Page, base_url: str) -> None:
    # The button ships hidden in markup; without site.js it must never
    # surface — a no-JS reader gets no dead control.
    page.route("**/assets/site.js", lambda route: route.abort())
    page.goto(
        f"{base_url}/nyc-taxi-demand-forecasting/model-evaluation.html",
        wait_until="networkidle",
    )
    page.unroute("**/assets/site.js")
    expect(page.locator(".back-to-top")).not_to_be_visible()


_MOBILE_VIEWPORT = {"width": 390, "height": 820}
_MOBILE_TOC_PAGE = "/nyc-taxi-demand-forecasting/model-evaluation.html"


def _open_mobile_toc(page: Page, base_url: str) -> Locator:
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{base_url}{_MOBILE_TOC_PAGE}", wait_until="networkidle")
    mobile_toc = page.locator(".mobile-toc")
    mobile_toc.locator("summary").click()
    return mobile_toc


def _assert_mobile_toc_disclosure(page: Page, base_url: str) -> None:
    # ≤58rem the aside TOC is replaced by the disclosure at article top;
    # at 390px the mobile menu test already pins this breakpoint working.
    mobile_toc = page.locator(".mobile-toc")
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{base_url}{_MOBILE_TOC_PAGE}", wait_until="networkidle")
    expect(mobile_toc).to_be_visible()
    expect(page.locator(".article-toc")).not_to_be_visible()
    expect(mobile_toc.locator("summary")).to_contain_text("On this page")
    expect(mobile_toc.locator("nav a").first).not_to_be_visible()

    mobile_toc.locator("summary").click()
    assert mobile_toc.get_attribute("open") is not None
    expect(mobile_toc.locator("nav a").first).to_be_visible()


def _assert_mobile_toc_link_pick_closes(page: Page, base_url: str) -> None:
    mobile_toc = _open_mobile_toc(page, base_url)
    first_link = mobile_toc.locator("nav a").first
    href = first_link.get_attribute("href")
    assert href and href.startswith("#")
    first_link.click()
    assert page.url.endswith(href)
    assert mobile_toc.get_attribute("open") is None


def _assert_mobile_toc_closes_on_escape_and_outside_click(
    page: Page, base_url: str
) -> None:
    mobile_toc = _open_mobile_toc(page, base_url)
    page.keyboard.press("Escape")
    assert mobile_toc.get_attribute("open") is None

    mobile_toc.locator("summary").click()
    assert mobile_toc.get_attribute("open") is not None
    page.locator(".article h1").click()
    assert mobile_toc.get_attribute("open") is None


def _assert_mobile_toc_localizes(page: Page, base_url: str) -> None:
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(
        f"{base_url}/pt-BR{_MOBILE_TOC_PAGE}",
        wait_until="networkidle",
    )
    expect(page.locator(".mobile-toc summary")).to_contain_text("Nesta pagina")


def _assert_mobile_toc_hidden_on_desktop(page: Page, base_url: str) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(f"{base_url}{_MOBILE_TOC_PAGE}", wait_until="networkidle")
    expect(page.locator(".mobile-toc")).not_to_be_visible()
    expect(page.locator(".article-toc")).to_be_visible()


def _assert_mobile_toc_works_without_js(page: Page, base_url: str) -> None:
    # <details> toggles natively, so a no-JS reader still reaches the TOC;
    # only the close conveniences (link pick, outside click, Escape) go away.
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.route("**/assets/site.js", lambda route: route.abort())
    page.goto(f"{base_url}{_MOBILE_TOC_PAGE}", wait_until="networkidle")
    page.unroute("**/assets/site.js")
    mobile_toc = page.locator(".mobile-toc")
    expect(mobile_toc).to_be_visible()
    mobile_toc.locator("summary").click()
    assert mobile_toc.get_attribute("open") is not None


_ARTICLE_PAGE = "/nyc-taxi-demand-forecasting/overview.html"
_EDIT_BASE = "https://github.com/dmenezesgabriel/mlops/edit/master/"


def _assert_page_meta_english(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}{_ARTICLE_PAGE}", wait_until="networkidle")
    meta = page.locator(".page-meta")
    expect(meta).to_be_visible()

    edit_link = meta.locator(".edit-link")
    expect(edit_link).to_contain_text("Edit page")
    href = edit_link.get_attribute("href")
    assert href and href.startswith(_EDIT_BASE)

    time = meta.locator("time")
    expect(time).to_be_visible()
    expect(time).to_have_attribute(
        "datetime", re.compile(r"\d{4}-\d{2}-\d{2}")
    )
    expect(meta).to_contain_text("Last updated:")


def _assert_page_meta_pt_br(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/pt-BR{_ARTICLE_PAGE}", wait_until="networkidle")
    meta = page.locator(".page-meta")
    expect(meta.locator(".edit-link")).to_contain_text("Editar página")
    expect(meta).to_contain_text("Última atualização:")
    # The pt-BR page renders a generated .ssg intermediate; its edit link
    # must still resolve to the authored source file.
    href = meta.locator(".edit-link").get_attribute("href")
    assert href and href.startswith(_EDIT_BASE)
    assert ".ssg" not in href


def _assert_page_meta_sits_above_pager(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}{_ARTICLE_PAGE}", wait_until="networkidle")
    # DOCUMENT_POSITION_FOLLOWING (4): the pager must follow the meta row.
    position = page.evaluate(
        "() => document.querySelector('.page-meta')"
        ".compareDocumentPosition(document.querySelector('.pager'))"
    )
    assert position & 4


def _assert_page_meta_visible_without_js(page: Page, base_url: str) -> None:
    # The meta row is static markup: a no-JS reader still gets both fields.
    page.route("**/assets/site.js", lambda route: route.abort())
    page.goto(f"{base_url}{_ARTICLE_PAGE}", wait_until="networkidle")
    page.unroute("**/assets/site.js")
    expect(page.locator(".page-meta")).to_be_visible()
    expect(page.locator(".page-meta time")).to_be_visible()


def _configured_paths() -> tuple[str, ...]:
    # Keep in sync with slugs listed in site/site.yaml → pages[].slug
    return (
        "/",
        "/nyc-taxi-demand-forecasting/overview.html",
        "/nyc-taxi-demand-forecasting/problem-framing.html",
        "/nyc-taxi-demand-forecasting/data-collection.html",
        "/nyc-taxi-demand-forecasting/exploratory-data-analysis.html",
        "/nyc-taxi-demand-forecasting/data-preprocessing.html",
        "/nyc-taxi-demand-forecasting/feature-engineering.html",
        "/nyc-taxi-demand-forecasting/model-training.html",
        "/pt-BR/",
        "/pt-BR/nyc-taxi-demand-forecasting/overview.html",
    )
