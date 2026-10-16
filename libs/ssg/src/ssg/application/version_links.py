from dataclasses import replace
from pathlib import Path

from ssg.application.variant_links import relative_href
from ssg.domain import SiteVariant, VersionLink


def version_links_for(
    current_variant: SiteVariant, current_directory: Path
) -> tuple[VersionLink, ...]:
    """Header-switcher links to every declared version's same-locale root.

    Example: a page at `out/0.2/pt-BR/coll/p.html` links to
    `../../../0.1/pt-BR/index.html` for version 0.1 — the switcher's static
    hrefs point at version roots (material templates/version/index.tsx:62);
    same-page switching is a JS enhancement.
    """
    site = current_variant.site
    versioning = site.versioning
    if versioning is None:
        return ()
    # variant.output_path is the locale root; its parent is the version
    # dir, whose parent is the build root.
    version_root = (
        current_variant.output_path.parent
        if site.locale != site.default_locale
        else current_variant.output_path
    )
    locale_segment = "" if site.locale == site.default_locale else site.locale
    links: list[VersionLink] = []
    for entry in versioning.versions:
        if entry.hidden:
            continue
        target_root = _target_root(version_root, entry.id, locale_segment)
        # A declared version whose tree never landed must not produce a
        # dead switcher link; the dir's presence is the deployment record
        # (mike's versions.json lists only deployed versions).
        if not target_root.is_dir():
            continue
        links.append(
            VersionLink(
                label=entry.title,
                href=relative_href(
                    current_directory, target_root / "index.html"
                ),
                version_id=entry.id,
                current=entry.id == site.version,
                alias=entry.aliases[0] if entry.aliases else None,
            )
        )
    return tuple(links)


def not_found_version_links(
    current_variant: SiteVariant,
) -> tuple[VersionLink, ...]:
    """404 switcher links — absolute when site.url is set, the same
    convention `absolute_navigation`/`not_found_language_links` follow:
    hosts serve a 404 at the missing path's depth, where relative hrefs
    would resolve against the wrong directory, and the default version's
    copy is additionally mirrored to the output root."""
    site = current_variant.site
    versioning = site.versioning
    if versioning is None:
        return ()
    links = version_links_for(current_variant, current_variant.output_path)
    if not site.url:
        return links
    locale = "" if site.locale == site.default_locale else f"{site.locale}/"
    return tuple(
        replace(
            link,
            href=(
                f"{site.url.rstrip('/')}/{link.version_id}/{locale}index.html"
            ),
        )
        for link in links
    )


def _target_root(version_root: Path, version_id: str, locale: str) -> Path:
    target = version_root.parent / version_id
    if locale:
        return target / locale
    return target
