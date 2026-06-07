from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urldefrag

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.playwright
class TestBuiltSiteSmoke:
    def test_built_site_supports_navigation_i18n_and_mobile_menu(
        self,
        page: Page,
    ) -> None:
        # Arrange
        site_build_path = Path("site/build")
        if not site_build_path.exists():
            site_build_path = Path("../../site/build")
        assert (
            site_build_path.exists()
        ), "Missing site/build: expected `make build-site` before e2e"

        # Act & Assert
        with _serve_directory(site_build_path) as base_url:
            _assert_home_page(page, base_url)
            _assert_language_switcher(page, base_url)
            _assert_configured_pages(page, base_url)
            _assert_notebook_and_code_pages(page, base_url)
            _assert_static_assets(page, base_url)
            _assert_mobile_menu(page, base_url)


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
        assert (
            response.status < 400
        ), f"{path} links to {link_without_fragment}"


def _assert_notebook_and_code_pages(page: Page, base_url: str) -> None:
    notebook_path = (
        "/nyc-taxi-demand-forecasting/feature-engineering-notebook.html"
    )
    page.goto(f"{base_url}{notebook_path}", wait_until="networkidle")
    expect(page.locator(".notebook-cell").first).to_be_visible()
    # Notebook rendering uses `.notebook-input` for code cells in the current
    # renderer; assert its visibility rather than the deprecated `.source-panel`.
    expect(page.locator(".notebook-input").first).to_be_visible()
    expect(page.locator(".highlight-token").first).to_be_visible()

    code_path = (
        "/nyc-taxi-demand-forecasting/feature-store-with-feast-duckdb.html"
    )
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


def _configured_paths() -> tuple[str, ...]:
    return (
        "/",
        "/nyc-taxi-demand-forecasting/overview.html",
        "/nyc-taxi-demand-forecasting/problem-framing.html",
        "/nyc-taxi-demand-forecasting/dataset-collection.html",
        "/nyc-taxi-demand-forecasting/event-logs-to-supervised-learning.html",
        "/nyc-taxi-demand-forecasting/feature-store-with-feast-duckdb.html",
        "/nyc-taxi-demand-forecasting/feature-engineering-notebook.html",
        "/nyc-taxi-demand-forecasting/mlflow-model-registry.html",
        "/pt-BR/",
        "/pt-BR/nyc-taxi-demand-forecasting/overview.html",
    )


@contextmanager
def _serve_directory(directory: Path) -> Iterator[str]:
    class QuietHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
