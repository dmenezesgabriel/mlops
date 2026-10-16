"""Browser-level checks for the versioned output layout and switcher."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.playwright
class TestBuiltSiteVersioning:
    def test_root_redirects_to_the_default_version(
        self, page: Page, site_root_url: str, site_version: str
    ) -> None:
        # Request rather than navigate: the stub's meta-refresh would follow
        # immediately and hide the markup under test.
        response = page.request.get(f"{site_root_url}/")

        assert response.ok
        body = response.text()
        assert f'content="0; url=./{site_version}/"' in body
        assert (
            f'href="https://dmenezesgabriel.github.io/mlops/{site_version}/"'
            in body
        )

    def test_versions_registry_lists_the_current_version(
        self, page: Page, site_root_url: str, site_version: str
    ) -> None:
        response = page.request.get(f"{site_root_url}/versions.json")

        assert response.ok
        entries = response.json()
        assert [entry["version"] for entry in entries] == [site_version]
        assert "latest" in entries[0]["aliases"]

    def test_unversioned_content_path_is_not_served(
        self, page: Page, site_root_url: str
    ) -> None:
        # Publishing moved every content URL under the version segment; the
        # artifact root must not keep an unversioned copy.
        response = page.request.get(
            f"{site_root_url}/nyc-taxi-demand-forecasting/overview.html"
        )

        assert response.status == 404

    def test_version_switcher_marks_the_current_version(
        self, page: Page, site_root_url: str, site_version: str
    ) -> None:
        page.goto(
            f"{site_root_url}/{site_version}"
            "/nyc-taxi-demand-forecasting/overview.html",
            wait_until="networkidle",
        )
        switcher = page.locator("[data-version-switcher]")

        expect(switcher).to_be_visible()
        expect(switcher.locator(".version-switcher__current")).to_have_text(
            site_version
        )
        current = switcher.locator('a[aria-current="page"]')
        expect(current).to_have_attribute("data-version-segment", site_version)
        expect(current.locator(".version-switcher__alias")).to_have_text(
            "latest"
        )

    def test_alias_tree_mirrors_the_current_version(
        self, page: Page, site_root_url: str, site_version: str
    ) -> None:
        page.goto(
            f"{site_root_url}/latest"
            "/nyc-taxi-demand-forecasting/overview.html",
            wait_until="networkidle",
        )

        expect(page.locator("article h1")).to_be_visible()
        current = page.locator(
            '[data-version-switcher] a[aria-current="page"]'
        )
        expect(current).to_have_attribute("data-version-segment", site_version)
