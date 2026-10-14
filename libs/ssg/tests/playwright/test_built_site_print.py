import pytest
from playwright.sync_api import Page, expect


@pytest.mark.playwright
class TestBuiltSitePrint:
    def test_print_hides_chrome_and_widens_content(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        # Act & Assert
        _assert_print_hides_chrome(page, built_site_url)
        _assert_print_layout_is_article_column(page, built_site_url)

    def test_print_forces_light_readable_palette(
        self,
        page: Page,
        built_site_url: str,
    ) -> None:
        # Act & Assert
        _assert_print_ignores_dark_theme_pick(page, built_site_url)
        _assert_print_flattens_syntax_tokens(page, built_site_url)


_ARTICLE_PATH = "/nyc-taxi-demand-forecasting/model-evaluation.html"
# --ink light variant; source of truth is the :root palette in site.css.
_PRINT_INK = "rgb(21, 17, 13)"


def _assert_print_hides_chrome(page: Page, base_url: str) -> None:
    page.emulate_media(media="print")
    page.goto(f"{base_url}{_ARTICLE_PATH}", wait_until="networkidle")
    # Nav, on-page TOC, pager and the interactive header controls are dead
    # weight on paper; the article itself and the masthead stay.
    for selector in (
        ".sidebar",
        ".article-toc",
        ".pager",
        ".header-actions",
        ".skip-link",
    ):
        expect(page.locator(selector)).not_to_be_visible()
    expect(page.locator(".article")).to_be_visible()
    expect(page.locator(".site-header")).to_be_visible()


def _assert_print_layout_is_article_column(page: Page, base_url: str) -> None:
    page.emulate_media(media="print")
    page.goto(f"{base_url}{_ARTICLE_PATH}", wait_until="networkidle")
    header_position = page.locator(".site-header").evaluate(
        "el => getComputedStyle(el).position"
    )
    assert header_position == "static"
    shell_display = page.locator(".site-shell").evaluate(
        "el => getComputedStyle(el).display"
    )
    assert shell_display == "block"


def _assert_print_ignores_dark_theme_pick(page: Page, base_url: str) -> None:
    # A stored dark pick must still print light: every themed color resolves
    # through light-dark(), which follows the element's color-scheme.
    page.emulate_media(media="print", color_scheme="dark")
    page.goto(f"{base_url}{_ARTICLE_PATH}", wait_until="networkidle")
    page.evaluate("() => { document.body.dataset.theme = 'dark'; }")
    body_color = page.evaluate("() => getComputedStyle(document.body).color")
    assert body_color == _PRINT_INK


def _assert_print_flattens_syntax_tokens(page: Page, base_url: str) -> None:
    # gruvbox-dark token colors land as inline styles; on paper they must
    # collapse to ink and long lines must wrap instead of clipping.
    page.emulate_media(media="print")
    page.goto(f"{base_url}{_ARTICLE_PATH}", wait_until="networkidle")
    pre = page.locator(".article-body pre").first
    assert pre.evaluate("el => getComputedStyle(el).color") == _PRINT_INK
    assert pre.evaluate("el => getComputedStyle(el).whiteSpace") == "pre-wrap"
    token = page.locator(".highlight-token").first
    assert token.evaluate("el => getComputedStyle(el).color") == _PRINT_INK
