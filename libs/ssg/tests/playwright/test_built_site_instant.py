import pytest
from playwright.sync_api import Page, expect

_ARTICLE_PATH = "/nyc-taxi-demand-forecasting/overview.html"
# Sidebar hrefs are page-relative (no leading slash); URL assertions use
# the absolute _ARTICLE_PATH, click/hover selectors the bare fragment.
_OVERVIEW_FRAGMENT = "overview.html"


@pytest.mark.playwright
class TestBuiltSiteInstantNavigation:
    def test_internal_click_swaps_content_without_reload(
        self, page: Page, built_site_url: str
    ) -> None:
        _assert_swap_without_reload(page, built_site_url)

    def test_search_theme_and_scrollspy_remount_after_swap(
        self, page: Page, built_site_url: str
    ) -> None:
        _assert_search_remounts_after_swap(page, built_site_url)
        _assert_theme_remounts_after_swap(page, built_site_url)
        _assert_scrollspy_remounts_after_swap(page, built_site_url)

    def test_back_button_restores_previous_page_and_scroll(
        self, page: Page, built_site_url: str
    ) -> None:
        _assert_back_restores_page_and_scroll(page, built_site_url)

    def test_hover_prefetches_internal_link(
        self, page: Page, built_site_url: str
    ) -> None:
        _assert_hover_prefetches(page, built_site_url)

    def test_out_of_sitemap_and_failed_fetches_navigate_normally(
        self, page: Page, built_site_url: str
    ) -> None:
        _assert_cross_locale_link_reloads(page, built_site_url)
        _assert_failed_fetch_falls_back(page, built_site_url)

    def test_navigation_degrades_without_js(
        self, page: Page, built_site_url: str
    ) -> None:
        _assert_native_navigation_without_js(page, built_site_url)


def _plant_reload_probe(page: Page) -> None:
    # A full reload wipes window state; a content swap keeps it. The probe
    # tells the two apart without depending on timing.
    page.evaluate("() => { window.__ssgSwapProbe = 'alive'; }")


def _probe_alive(page: Page) -> bool:
    return page.evaluate("() => window.__ssgSwapProbe === 'alive'")


def _click_first_nav_link_to(page: Page, path_fragment: str) -> None:
    page.locator(f"#site-navigation a[href*='{path_fragment}']").first.click()


def _assert_swap_without_reload(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)
    _click_first_nav_link_to(page, "overview.html")

    expect(page).to_have_url(f"{base_url}{_ARTICLE_PATH}")
    expect(page.locator(".article")).to_contain_text("Overview")
    expect(page).to_have_title("Overview - NYC Taxi Demand Forecasting")
    expect(
        page.locator("#site-navigation a[aria-current='page']")
    ).to_contain_text("Overview")
    assert _probe_alive(page), "expected a content swap, not a full reload"

    # The same swap must work inside the pt-BR variant, whose sitemap and
    # search index live under the locale prefix.
    page.goto(f"{base_url}/pt-BR/", wait_until="networkidle")
    _plant_reload_probe(page)
    _click_first_nav_link_to(page, "overview.html")
    expect(page.locator(".article")).to_contain_text("Visao Geral")
    assert _probe_alive(page), "expected a content swap, not a full reload"


def _assert_search_remounts_after_swap(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)
    _click_first_nav_link_to(page, "overview.html")
    expect(page.locator(".article")).to_contain_text("Overview")

    page.locator(".search-input").fill("taxi")
    expect(page.locator(".search-results li a").first).to_be_visible()


def _assert_theme_remounts_after_swap(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)
    _click_first_nav_link_to(page, "overview.html")
    expect(page.locator(".article")).to_contain_text("Overview")

    page.locator(".theme-select").select_option("dark")
    expect(page.locator("body")).to_have_attribute("data-theme", "dark")


def _assert_scrollspy_remounts_after_swap(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)
    # The index sidebar links only the collection's entry page; the second
    # hop reaches the TOC-bearing page through another swap.
    _click_first_nav_link_to(page, "overview.html")
    expect(page.locator(".article")).to_contain_text("Overview")
    _click_first_nav_link_to(page, "model-evaluation.html")
    # The h1 is the arrival probe: overview's article body already contains
    # the word "Evaluate", so a body-text check passes before the swap lands.
    expect(page.locator(".article h1")).to_have_text("Evaluate")

    toc_links = page.locator(".article-toc a[href^='#']")
    second_href = toc_links.nth(1).get_attribute("href")
    assert second_href
    _scroll_heading_into_pick_band(page, second_href)
    expect(toc_links.nth(1)).to_have_attribute("aria-current", "true")


def _assert_back_restores_page_and_scroll(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}{_ARTICLE_PATH}", wait_until="networkidle")
    page.evaluate("() => window.scrollTo({ top: 800, behavior: 'instant' })")
    # The offset lands in history.state only after the debounced save.
    page.wait_for_function("() => history.state && history.state.y === 800")

    _click_first_nav_link_to(page, "model-evaluation.html")
    expect(page.locator(".article h1")).to_have_text("Evaluate")

    page.go_back()
    expect(page.locator(".article")).to_contain_text("Overview")
    page.wait_for_function("() => window.scrollY === 800")


def _assert_hover_prefetches(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)
    prefetched: list[str] = []
    page.on("request", lambda request: prefetched.append(request.url))

    page.locator(
        f"#site-navigation a[href*='{_OVERVIEW_FRAGMENT}']"
    ).first.hover()
    page.wait_for_timeout(500)

    assert any(_ARTICLE_PATH in url for url in prefetched), (
        f"expected a prefetch request for {_ARTICLE_PATH}: {prefetched}"
    )
    assert _probe_alive(page), "prefetch must not navigate away"


def _assert_cross_locale_link_reloads(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}{_ARTICLE_PATH}", wait_until="networkidle")
    _plant_reload_probe(page)
    page.locator(".language-switcher summary").click()
    page.locator(".language-switcher a[href*='pt-BR']").click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("html")).to_have_attribute("lang", "pt-BR")
    assert not _probe_alive(page), "expected a full reload across locales"


def _assert_failed_fetch_falls_back(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)
    # Settle the hover prefetch first: its 25ms timer must not race the
    # route registration, or the prefetch would consume the "first request"
    # slot meant for the navigation fetch.
    page.locator(
        f"#site-navigation a[href*='{_OVERVIEW_FRAGMENT}']"
    ).first.hover()
    page.wait_for_timeout(200)

    attempts = {"count": 0}

    def fail_first_request(route) -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            route.abort()
        else:
            route.continue_()

    page.route(f"**{_ARTICLE_PATH}", fail_first_request)
    _click_first_nav_link_to(page, "overview.html")

    expect(page.locator(".article")).to_contain_text("Overview")
    assert not _probe_alive(page), "expected the fallback to fully reload"


def _assert_native_navigation_without_js(page: Page, base_url: str) -> None:
    page.route("**/assets/site.js", lambda route: route.abort())
    page.route("**/assets/instant.js", lambda route: route.abort())
    page.goto(f"{base_url}/", wait_until="networkidle")
    _plant_reload_probe(page)

    _click_first_nav_link_to(page, "overview.html")
    expect(page.locator(".article")).to_contain_text("Overview")
    assert not _probe_alive(page), "expected native navigation without JS"


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
