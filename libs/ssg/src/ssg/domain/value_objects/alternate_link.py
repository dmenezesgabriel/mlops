from dataclasses import dataclass

from ssg.domain.value_objects.site_variant import SiteVariant


@dataclass(frozen=True)
class AlternateLink:
    hreflang: str
    href: str


def alternate_links_for(
    site_variants: tuple[SiteVariant, ...], canonical_path: str
) -> tuple[AlternateLink, ...]:
    """Absolute `rel="alternate"` hreflang links for a locale-relative path.

    Example: ``alternate_links_for(variants, "guide/intro.html")`` yields
    one link per variant plus an ``x-default`` pointing at the default
    locale's URL.
    """
    if len(site_variants) < 2 or not site_variants[0].site.url:
        return ()
    default_variant = next(
        (
            variant
            for variant in site_variants
            if variant.site.locale == site_variants[0].site.default_locale
        ),
        site_variants[0],
    )
    return (
        *(
            AlternateLink(
                hreflang=variant.site.locale,
                href=variant.site.absolute_url(canonical_path),
            )
            for variant in site_variants
        ),
        AlternateLink(
            hreflang="x-default",
            href=default_variant.site.absolute_url(canonical_path),
        ),
    )
