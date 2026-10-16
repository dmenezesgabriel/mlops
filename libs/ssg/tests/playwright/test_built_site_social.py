"""Browser-level checks for build-time generated social cards."""

from io import BytesIO

import pytest
from PIL import Image
from playwright.sync_api import Page, expect


@pytest.mark.playwright
class TestBuiltSiteSocialCards:
    def test_generated_card_is_a_valid_1200x630_png(
        self, page: Page, built_site_url: str
    ) -> None:
        for image_path in (
            "assets/social/index.png",
            "assets/social/nyc-taxi-demand-forecasting/overview.png",
            "pt-BR/assets/social/nyc-taxi-demand-forecasting/overview.png",
        ):
            response = page.request.get(f"{built_site_url}/{image_path}")
            assert response.ok, f"{image_path}: {response.status}"
            image = Image.open(BytesIO(response.body()))
            assert image.size == (1200, 630), image_path
            assert image.format == "PNG"

    def test_cards_differ_between_pages_and_locales(
        self, page: Page, built_site_url: str
    ) -> None:
        paths = [
            "assets/social/index.png",
            "assets/social/nyc-taxi-demand-forecasting/overview.png",
            "pt-BR/assets/social/nyc-taxi-demand-forecasting/overview.png",
        ]
        bodies = [
            page.request.get(f"{built_site_url}/{path}").body()
            for path in paths
        ]
        assert len({bytes(body) for body in bodies}) == len(bodies)

    def test_not_found_keeps_static_image_fallback(
        self, page: Page, built_site_url: str
    ) -> None:
        page.goto(f"{built_site_url}/404.html", wait_until="networkidle")
        expect(page.locator('meta[property="og:image"]')).to_have_attribute(
            "content",
            "https://dmenezesgabriel.github.io/mlops/"
            "assets/mlops_lifecycle.png",
        )
