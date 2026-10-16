import pytest
from playwright.sync_api import BrowserContext, Page, expect

_ARTICLE_PATH = "/nyc-taxi-demand-forecasting/overview.html"


@pytest.mark.playwright
class TestBuiltSiteOffline:
    def test_pages_load_offline_after_precache(
        self, page: Page, context: BrowserContext, built_site_url: str
    ) -> None:
        _assert_offline_page_load(
            page, context, built_site_url, "", "Overview"
        )
        _assert_offline_page_load(
            page, context, built_site_url, "/pt-BR", "Visao Geral"
        )

    def test_instant_swap_works_offline(
        self, page: Page, context: BrowserContext, built_site_url: str
    ) -> None:
        _assert_offline_instant_swap(page, context, built_site_url)

    def test_search_works_offline(
        self, page: Page, context: BrowserContext, built_site_url: str
    ) -> None:
        _assert_offline_search(page, context, built_site_url)


def _wait_for_service_worker(page: Page) -> None:
    # ready resolves after activate (whose waitUntil includes the precache
    # install and clients.claim()), so afterwards the page is controlled and
    # its navigations hit the precache once the network drops.
    page.evaluate("async () => { await navigator.serviceWorker.ready; }")
    page.wait_for_function("() => navigator.serviceWorker.controller !== null")


def _assert_offline_page_load(
    page: Page,
    context: BrowserContext,
    base_url: str,
    locale_prefix: str,
    heading: str,
) -> None:
    page.goto(f"{base_url}{locale_prefix}/", wait_until="networkidle")
    _wait_for_service_worker(page)

    context.set_offline(True)
    page.goto(
        f"{base_url}{locale_prefix}{_ARTICLE_PATH}",
        wait_until="domcontentloaded",
    )
    expect(page.locator(".article")).to_contain_text(heading)
    expect(page.locator("#site-navigation")).to_be_visible()
    context.set_offline(False)


def _assert_offline_instant_swap(
    page: Page, context: BrowserContext, base_url: str
) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _wait_for_service_worker(page)
    # A full reload wipes window state; a content swap keeps it. The probe
    # tells the two apart without depending on timing.
    page.evaluate("() => { window.__ssgSwapProbe = 'alive'; }")

    context.set_offline(True)
    page.locator("#site-navigation a[href*='overview.html']").first.click()

    expect(page).to_have_url(f"{base_url}{_ARTICLE_PATH}")
    expect(page.locator(".article")).to_contain_text("Overview")
    assert page.evaluate("() => window.__ssgSwapProbe === 'alive'"), (
        "expected a cached content swap, not a reload"
    )
    context.set_offline(False)


def _assert_offline_search(
    page: Page, context: BrowserContext, base_url: str
) -> None:
    page.goto(f"{base_url}/", wait_until="networkidle")
    _wait_for_service_worker(page)

    context.set_offline(True)
    # search-index.json is precached, so the index fetch resolves from the
    # worker cache and ranking runs client-side as usual.
    page.locator(".search-input").fill("taxi")
    expect(page.locator(".search-results li a").first).to_be_visible()
    context.set_offline(False)
