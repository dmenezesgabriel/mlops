import os
from dataclasses import replace
from pathlib import Path

from ssg.domain import (
    ContentCollection,
    LanguageLink,
    NavigationSection,
    Page,
    Site,
    SiteNavigation,
    SiteVariant,
)


def index_language_links(
    current_variant: SiteVariant,
    site_variants: tuple[SiteVariant, ...],
) -> tuple[LanguageLink, ...]:
    return tuple(
        LanguageLink(
            label=site_variant.site.locale,
            href=relative_href(
                current_variant.output_path,
                site_variant.output_path / "index.html",
            ),
            current=site_variant.site.locale == current_variant.site.locale,
        )
        for site_variant in site_variants
    )


def page_language_links(
    current_variant: SiteVariant,
    site_variants: tuple[SiteVariant, ...],
    collection: ContentCollection,
    page: Page,
) -> tuple[LanguageLink, ...]:
    current_directory = current_variant.output_path / collection.output_slug
    return tuple(
        _page_language_link(
            current_variant,
            site_variant,
            current_directory,
            collection,
            page,
        )
        for site_variant in site_variants
    )


def not_found_language_links(
    current_variant: SiteVariant,
    site_variants: tuple[SiteVariant, ...],
) -> tuple[LanguageLink, ...]:
    return tuple(
        LanguageLink(
            label=site_variant.site.locale,
            href=_not_found_href(current_variant, site_variant),
            current=site_variant.site.locale == current_variant.site.locale,
        )
        for site_variant in site_variants
    )


def absolute_navigation(
    navigation: SiteNavigation, site: Site
) -> SiteNavigation:
    # Hosts serve the root 404.html for missing paths at any depth
    # (e.g. GitHub Pages answers /docs/a/b/c with it), so hrefs must not
    # resolve relative to the missing path's directory — with site.url
    # set they are emitted absolute, matching starlight's site-absolute
    # links; without one they stay relative, like mkdocs' 404.
    if not site.url:
        return navigation
    return SiteNavigation(
        home_href=site.absolute_url(navigation.home_href),
        sections=tuple(
            _absolute_section(section, site) for section in navigation.sections
        ),
    )


def _absolute_section(
    section: NavigationSection, site: Site
) -> NavigationSection:
    # navigation_for(None, None, ...) leaves section.links empty — page
    # links only exist in a current-collection context — so only the
    # section href needs rewriting.
    return replace(section, href=site.absolute_url(section.href))


def _not_found_href(
    current_variant: SiteVariant, target_variant: SiteVariant
) -> str:
    if target_variant.site.url:
        return target_variant.site.absolute_url("404.html")
    return relative_href(
        current_variant.output_path,
        target_variant.output_path / "404.html",
    )


def _page_language_link(
    current_variant: SiteVariant,
    target_variant: SiteVariant,
    current_directory: Path,
    collection: ContentCollection,
    page: Page,
) -> LanguageLink:
    target_path = (
        target_variant.output_path / collection.output_slug / page.file_name()
    )
    return LanguageLink(
        label=target_variant.site.locale,
        href=relative_href(current_directory, target_path),
        current=target_variant.site.locale == current_variant.site.locale,
    )


def relative_href(current_directory: Path, target_path: Path) -> str:
    return Path(os.path.relpath(target_path, current_directory)).as_posix()
