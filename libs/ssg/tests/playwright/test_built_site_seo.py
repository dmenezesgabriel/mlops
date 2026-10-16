from pathlib import Path

import pytest
import yaml
from playwright.sync_api import Page, expect


@pytest.mark.playwright
class TestBuiltSiteSeo:
    def test_built_site_head_carries_twitter_hreflang_and_og_image(
        self, page: Page, built_site_url: str
    ) -> None:
        site_url, site_title, site_description = _site_config_values()
        _assert_head_block(
            page,
            built_site_url,
            site_url,
            page_path="",
            image_url=f"{site_url}/assets/social/index.png",
            title=site_title,
            description=site_description,
        )
        _assert_head_block(
            page,
            built_site_url,
            site_url,
            page_path="nyc-taxi-demand-forecasting/overview.html",
            image_url=(
                f"{site_url}/assets/social/"
                "nyc-taxi-demand-forecasting/overview.png"
            ),
            title=None,
            description=site_description,
        )
        _assert_head_block(
            page,
            built_site_url,
            site_url,
            page_path="pt-BR/nyc-taxi-demand-forecasting/overview.html",
            image_url=(
                f"{site_url}/pt-BR/assets/social/"
                "nyc-taxi-demand-forecasting/overview.png"
            ),
            title=None,
            description=None,
        )

    def test_built_site_image_is_served_per_locale(
        self, page: Page, built_site_url: str
    ) -> None:
        for image_path in (
            "assets/mlops_lifecycle.png",
            "pt-BR/assets/mlops_lifecycle.png",
            "assets/social/index.png",
            "pt-BR/assets/social/index.png",
            ("assets/social/nyc-taxi-demand-forecasting/overview.png"),
            ("pt-BR/assets/social/nyc-taxi-demand-forecasting/overview.png"),
        ):
            response = page.request.get(f"{built_site_url}/{image_path}")
            assert response.ok, (
                f"expected {image_path} to be served: {response.status}"
            )


def _site_config_values() -> tuple[str, str, str]:
    site_config_path = Path("site/site.yaml")
    if not site_config_path.exists():
        site_config_path = Path("../../site/site.yaml")
    site_config = yaml.safe_load(site_config_path.read_text())
    site = site_config["site"]
    return site["url"].rstrip("/"), site["title"], site["description"]


def _assert_head_block(
    page: Page,
    base_url: str,
    site_url: str,
    page_path: str,
    image_url: str,
    title: str | None,
    description: str | None,
) -> None:
    page.goto(f"{base_url}/{page_path}", wait_until="networkidle")
    expect(page.locator('meta[name="twitter:card"]')).to_have_attribute(
        "content", "summary_large_image"
    )
    expect(page.locator('meta[name="twitter:title"]')).to_have_count(1)
    expect(page.locator('meta[name="twitter:description"]')).to_have_count(1)
    if title is not None:
        expect(page.locator('meta[name="twitter:title"]')).to_have_attribute(
            "content", title
        )
    if description is not None:
        expect(
            page.locator('meta[name="twitter:description"]')
        ).to_have_attribute("content", description)
    _assert_alternates(page, site_url, page_path)
    expect(page.locator('meta[property="og:image"]')).to_have_attribute(
        "content", image_url
    )
    expect(page.locator('meta[name="twitter:image"]')).to_have_attribute(
        "content", image_url
    )
    if image_url.endswith(".png") and "/social/" in image_url:
        # Generated cards carry the fixed Open Graph image geometry.
        expect(
            page.locator('meta[property="og:image:width"]')
        ).to_have_attribute("content", "1200")
        expect(
            page.locator('meta[property="og:image:height"]')
        ).to_have_attribute("content", "630")
        expect(
            page.locator('meta[property="og:image:type"]')
        ).to_have_attribute("content", "image/png")


def _assert_alternates(page: Page, site_url: str, page_path: str) -> None:
    # canonical_path is locale-relative, so the same alternate set lands on
    # every locale's page; x-default points at the default (en) URL.
    locale_path = page_path.removeprefix("pt-BR/")
    expected = {
        "en": f"{site_url}/{locale_path}",
        "pt-BR": f"{site_url}/pt-BR/{locale_path}",
        "x-default": f"{site_url}/{locale_path}",
    }
    for hreflang, href in expected.items():
        link = page.locator(f'link[rel="alternate"][hreflang="{hreflang}"]')
        expect(link).to_have_count(1)
        expect(link).to_have_attribute("href", href)
