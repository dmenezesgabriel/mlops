"""Browser checks for build-time rendered Mermaid diagrams."""

import pytest
from playwright.sync_api import Page, expect

_MERMAID_PATHS = (
    "/nyc-taxi-demand-forecasting/problem-framing.html",
    "/pt-BR/nyc-taxi-demand-forecasting/problem-framing.html",
)
# site.css resolves --surface through light-dark(): the diagram's
# themeCSS var() refs land on these concrete colors per scheme.
_SURFACE_LIGHT_RGB = "rgb(255, 249, 235)"
_SURFACE_DARK_RGB = "rgb(37, 30, 22)"


@pytest.mark.playwright
class TestBuiltSiteMermaid:
    @pytest.mark.parametrize("path", _MERMAID_PATHS)
    def test_mermaid_fence_renders_inline_svg(
        self, page: Page, built_site_url: str, path: str
    ) -> None:
        page.goto(f"{built_site_url}{path}", wait_until="networkidle")

        diagram = page.locator(".mermaid-diagram svg")
        expect(diagram).to_have_count(1)
        expect(diagram).to_be_visible()
        # Node labels carried through into the rendered svg — the bare
        # first <text> in document order is a marker-def sizing element.
        expect(diagram.locator(".node .label text").first).to_be_visible()
        # The source block is fully replaced: no fenced remnant stays
        # readable-as-code, and no JS was needed to draw anything.
        expect(page.locator("pre .language-mermaid")).to_have_count(0)
        expect(page.locator("pre.mermaid")).to_have_count(0)

    def test_mermaid_diagram_uses_site_palette(
        self, page: Page, built_site_url: str
    ) -> None:
        page.goto(
            f"{built_site_url}/nyc-taxi-demand-forecasting/problem-framing.html",
            wait_until="networkidle",
        )
        node = page.locator(".mermaid-diagram svg .node rect").first

        # themeCSS maps node fills to var(--surface); resolved through
        # light-dark(), the value tracks the active color-scheme.
        page.emulate_media(color_scheme="light")
        assert (
            node.evaluate("el => getComputedStyle(el).fill")
            == _SURFACE_LIGHT_RGB
        )

        page.emulate_media(color_scheme="dark")
        assert (
            node.evaluate("el => getComputedStyle(el).fill")
            == _SURFACE_DARK_RGB
        )

    def test_mermaid_diagram_does_not_overflow_mobile_viewport(
        self, page: Page, built_site_url: str
    ) -> None:
        page.set_viewport_size({"width": 320, "height": 820})
        page.goto(
            f"{built_site_url}/nyc-taxi-demand-forecasting/problem-framing.html",
            wait_until="networkidle",
        )

        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        assert scroll_width <= 320
