from pathlib import Path

from ssg.domain import (
    AlternateLink,
    Site,
    SiteVariant,
    alternate_links_for,
)


def _site(
    locale: str,
    url: str = "https://example.com/docs",
    default_locale: str = "en",
) -> Site:
    return Site(
        title="Site",
        description="",
        collections=(),
        locale=locale,
        default_locale=default_locale,
        url=url,
    )


def _variants(
    *locales: str, url: str = "https://example.com/docs"
) -> tuple[SiteVariant, ...]:
    root = Path("/out")
    return tuple(
        SiteVariant(
            site=_site(locale, url=url),
            output_path=root if locale == "en" else root / locale,
        )
        for locale in locales
    )


def test_alternate_links_for_lists_absolute_url_per_locale_and_x_default() -> (
    None
):
    # Arrange — a page's canonical_path is locale-relative, so each variant
    # prefixes it with its own locale root; x-default points at the default
    # locale's URL (starlight head.ts:80-101 parity).
    site_variants = _variants("en", "pt-BR")

    # Act
    links = alternate_links_for(
        site_variants, "sample-collection/overview.html"
    )

    # Assert
    assert links == (
        AlternateLink(
            hreflang="en",
            href="https://example.com/docs/sample-collection/overview.html",
        ),
        AlternateLink(
            hreflang="pt-BR",
            href="https://example.com/docs/pt-BR/"
            "sample-collection/overview.html",
        ),
        AlternateLink(
            hreflang="x-default",
            href="https://example.com/docs/sample-collection/overview.html",
        ),
    )


def test_alternate_links_for_returns_empty_for_single_variant() -> None:
    # Arrange — monolingual sites have nothing to alternate to (starlight's
    # isMultilingual gate).
    site_variants = _variants("en")

    # Act / Assert
    assert alternate_links_for(site_variants, "index.html") == ()


def test_alternate_links_for_returns_empty_without_site_url() -> None:
    # Arrange — hreflang hrefs must be absolute; no deployment URL means
    # nothing to emit (starlight's canonical gate).
    site_variants = _variants("en", "pt-BR", url="")

    # Act / Assert
    assert alternate_links_for(site_variants, "index.html") == ()


def test_alternate_links_for_falls_back_to_first_variant_for_x_default() -> (
    None
):
    # Arrange — a custom provider may ship no variant matching the shared
    # default_locale; the first variant then stands in as the default.
    site_variants = _variants("fr", "pt-BR")

    # Act
    links = alternate_links_for(site_variants, "")

    # Assert
    assert links[-1] == AlternateLink(
        hreflang="x-default", href="https://example.com/docs/fr/"
    )
