from collections.abc import Callable

import pytest
from playwright.sync_api import Page, Route, expect

# 404.html links assets by absolute site.url so hosts resolve them at any
# missing-path depth; the sweep redirects those requests to the local build.
_PRODUCTION_SITE_URL = "https://dmenezesgabriel.github.io/mlops"
_SWEEP_WIDTHS = (320, 390, 768)
_SWEEP_HEIGHT = 820
_ARTICLE_PATHS = (
    # Table page, code page, notebook page, and the longer pt-BR labels.
    "/nyc-taxi-demand-forecasting/exploratory-data-analysis.html",
    "/nyc-taxi-demand-forecasting/model-evaluation.html",
    "/nyc-taxi-demand-forecasting/feature-engineering.html",
    "/pt-BR/nyc-taxi-demand-forecasting/exploratory-data-analysis.html",
)
_SWEEP_PATHS = ("/", "/pt-BR/", *_ARTICLE_PATHS, "/404.html")
# Apple HIG 44pt; inline prose links are exempt (WCAG 2.5.8), so only the
# interactive chrome is held to it.
_MIN_TAP_TARGET_PX = 44
_TAP_TARGET_SELECTORS = (
    ".menu-toggle",
    ".language-switcher summary",
    ".theme-select",
    ".search-input",
    ".mobile-toc summary",
    ".pager a",
)
# iOS Safari zooms the page on focus of any form control below 16px.
_MIN_INPUT_FONT_PX = 16


@pytest.mark.playwright
class TestBuiltSiteResponsive:
    @pytest.mark.parametrize("width", _SWEEP_WIDTHS)
    def test_pages_have_no_horizontal_overflow(
        self, page: Page, built_site_url: str, width: int
    ) -> None:
        # Act
        failures = _sweep(page, built_site_url, width, _overflow_failures)

        # Assert
        assert not failures, "\n".join(failures)

    def test_pages_have_no_horizontal_overflow_without_js(
        self, page: Page, built_site_url: str
    ) -> None:
        # Act
        failures = _sweep(
            page, built_site_url, 320, _overflow_failures, block_js=True
        )

        # Assert
        assert not failures, "\n".join(failures)

    @pytest.mark.parametrize("width", _SWEEP_WIDTHS)
    def test_chrome_tap_targets_are_at_least_44px(
        self, page: Page, built_site_url: str, width: int
    ) -> None:
        # Act
        failures = _sweep(page, built_site_url, width, _tap_target_failures)

        # Assert
        assert not failures, "\n".join(failures)

    @pytest.mark.parametrize("width", _SWEEP_WIDTHS)
    def test_form_controls_are_at_least_16px(
        self, page: Page, built_site_url: str, width: int
    ) -> None:
        # Act
        failures = _sweep(page, built_site_url, width, _input_font_failures)

        # Assert
        assert not failures, "\n".join(failures)

    @pytest.mark.parametrize("width", _SWEEP_WIDTHS)
    def test_navigation_search_and_toc_are_reachable(
        self, page: Page, built_site_url: str, width: int
    ) -> None:
        # Act & Assert
        page.set_viewport_size({"width": width, "height": _SWEEP_HEIGHT})
        for path in _ARTICLE_PATHS:
            _assert_chrome_reachable(page, f"{built_site_url}{path}")


def _sweep(
    page: Page,
    base_url: str,
    width: int,
    measure: Callable[[Page], list[str]],
    *,
    block_js: bool = False,
) -> list[str]:
    page.set_viewport_size({"width": width, "height": _SWEEP_HEIGHT})
    if block_js:
        page.route("**/assets/site.js", lambda route: route.abort())

    def rewrite_production_assets(route: Route) -> None:
        url = route.request.url
        if block_js and url.endswith("/assets/site.js"):
            route.abort()
            return
        response = route.fetch(url=url.replace(_PRODUCTION_SITE_URL, base_url))
        route.fulfill(response=response)

    page.route(f"{_PRODUCTION_SITE_URL}/**", rewrite_production_assets)
    failures: list[str] = []
    for path in _SWEEP_PATHS:
        page.goto(f"{base_url}{path}", wait_until="networkidle")
        failures.extend(f"{width}px {path}: {f}" for f in measure(page))
    return failures


def _overflow_failures(page: Page) -> list[str]:
    scroll_width = page.evaluate("document.documentElement.scrollWidth")
    inner_width = page.evaluate("window.innerWidth")
    if scroll_width <= inner_width:
        return []
    return [f"scrollWidth {scroll_width} > innerWidth {inner_width}"]


def _tap_target_failures(page: Page) -> list[str]:
    failures: list[str] = []
    for selector in _TAP_TARGET_SELECTORS:
        failures.extend(_undersized_targets(page, selector))
    return failures


def _undersized_targets(page: Page, selector: str) -> list[str]:
    boxes = [
        element.bounding_box()
        for element in page.locator(selector).all()
        if element.is_visible()
    ]
    return [
        f"{selector} {box['width']:.1f}x{box['height']:.1f}px"
        f" (expected both >= {_MIN_TAP_TARGET_PX}px)"
        for box in boxes
        if box is not None
        and min(box["width"], box["height"]) < _MIN_TAP_TARGET_PX
    ]


def _input_font_failures(page: Page) -> list[str]:
    measured = page.locator("input, select, textarea").evaluate_all(
        """controls => controls
            .filter(control => control.checkVisibility())
            .map(control => [control.className,
                parseFloat(getComputedStyle(control).fontSize)])"""
    )
    return [
        f"{class_name} font-size {size}px (expected >= {_MIN_INPUT_FONT_PX}px)"
        for class_name, size in measured
        if size < _MIN_INPUT_FONT_PX
    ]


def _assert_chrome_reachable(page: Page, url: str) -> None:
    page.goto(url, wait_until="networkidle")
    expect(page.locator(".search-input")).to_be_visible()
    expect(page.locator(".mobile-toc summary")).to_be_visible()
    expect(page.locator("#site-navigation")).not_to_be_visible()
    page.locator(".menu-toggle").click()
    expect(page.locator("#site-navigation")).to_be_visible()
