from pathlib import Path

from ssg.application.version_links import (
    not_found_version_links,
    version_links_for,
)
from ssg.domain import Site, SiteVariant, SiteVersion, SiteVersioning


def _variant(
    output_root: Path,
    locale: str = "en",
    version: str = "0.2",
    extra_versions: tuple[SiteVersion, ...] = (),
    url: str = "",
) -> SiteVariant:
    output_path = output_root / version
    if locale != "en":
        output_path = output_path / locale
    site = Site(
        title="Learning Site",
        description="",
        collections=(),
        locale=locale,
        version=version,
        url=url,
        versioning=SiteVersioning(
            current=version,
            default="latest",
            versions=(
                SiteVersion(id="0.2", title="0.2", aliases=("latest",)),
                SiteVersion(id="0.1", title="0.1"),
                SiteVersion(id="0.0", title="0.0"),
                *extra_versions,
            ),
        ),
    )
    return SiteVariant(site=site, output_path=output_path)


def _deploy(output_root: Path, *version_ids: str) -> None:
    """Land each version's locale roots — the deployment record the
    switcher reads (a declared version with no dir is not linkable)."""
    for version_id in version_ids:
        (output_root / version_id / "pt-BR").mkdir(parents=True)


def test_version_links_point_at_each_versions_same_locale_root(
    tmp_path: Path,
) -> None:
    # Arrange — page dir mirrors the emitted <collection>/ page depth.
    _deploy(tmp_path, "0.2", "0.1")
    variant = _variant(tmp_path)
    current_directory = variant.output_path / "sample-collection"

    # Act
    links = version_links_for(variant, current_directory)

    # Assert — relative hrefs land on the target version's index, matching
    # material's `../<version>/` links (templates/version/index.tsx:62);
    # undeployed 0.0 is declared but has no tree, so no link.
    assert [(link.label, link.href) for link in links] == [
        ("0.2", "../index.html"),
        ("0.1", "../../0.1/index.html"),
    ]


def test_version_links_keep_the_non_default_locale(tmp_path: Path) -> None:
    # Arrange — a pt-BR page switches to the target version's pt-BR root.
    _deploy(tmp_path, "0.2", "0.1")
    variant = _variant(tmp_path, locale="pt-BR")
    current_directory = variant.output_path / "sample-collection"

    # Act
    links = version_links_for(variant, current_directory)

    # Assert
    assert [link.href for link in links] == [
        "../index.html",
        "../../../0.1/pt-BR/index.html",
    ]


def test_version_links_skip_undeployed_version_dirs(tmp_path: Path) -> None:
    # Arrange — only the current version's tree exists.
    _deploy(tmp_path, "0.2")
    variant = _variant(tmp_path)

    # Act
    links = version_links_for(variant, variant.output_path)

    # Assert
    assert [link.label for link in links] == ["0.2"]


def test_version_links_mark_the_current_version_and_alias(
    tmp_path: Path,
) -> None:
    # Arrange
    _deploy(tmp_path, "0.2", "0.1")
    variant = _variant(tmp_path, version="0.2")

    # Act
    links = version_links_for(variant, variant.output_path)

    # Assert — the alias surfaces as a badge on its owning version
    # (material's `aliases[0]` chip), never as its own list entry; the
    # version id rides along for the JS same-page resolver.
    assert [
        (link.label, link.version_id, link.current, link.alias)
        for link in links
    ] == [
        ("0.2", "0.2", True, "latest"),
        ("0.1", "0.1", False, None),
    ]


def test_version_links_skip_hidden_entries(tmp_path: Path) -> None:
    # Arrange — mike's properties.hidden keeps a deployed version out of
    # the selector without deleting its tree.
    _deploy(tmp_path, "0.2", "0.1", "0.0")
    hidden = (SiteVersion(id="9.9", title="9.9", hidden=True),)
    (tmp_path / "9.9").mkdir()
    variant = _variant(tmp_path, extra_versions=hidden)

    # Act
    links = version_links_for(variant, variant.output_path)

    # Assert
    assert [link.label for link in links] == ["0.2", "0.1", "0.0"]


def test_version_links_empty_when_unversioned(tmp_path: Path) -> None:
    # Arrange
    variant = SiteVariant(
        site=Site(title="Site", description="", collections=()),
        output_path=tmp_path,
    )

    # Act / Assert
    assert version_links_for(variant, variant.output_path) == ()


def test_not_found_version_links_go_absolute_when_site_url_set(
    tmp_path: Path,
) -> None:
    # Arrange — the root-copied 404 serves at any depth, so like
    # not_found_language_links it cannot rely on relative hrefs.
    _deploy(tmp_path, "0.2", "0.1")
    variant = _variant(tmp_path, url="https://example.test/docs")

    # Act
    links = not_found_version_links(variant)

    # Assert
    assert [link.href for link in links] == [
        "https://example.test/docs/0.2/index.html",
        "https://example.test/docs/0.1/index.html",
    ]


def test_not_found_version_links_stay_relative_without_site_url(
    tmp_path: Path,
) -> None:
    # Arrange
    _deploy(tmp_path, "0.2", "0.1")
    variant = _variant(tmp_path)

    # Act
    links = not_found_version_links(variant)

    # Assert
    assert [link.href for link in links] == [
        "index.html",
        "../0.1/index.html",
    ]


def test_not_found_version_links_keep_the_locale(tmp_path: Path) -> None:
    # Arrange
    _deploy(tmp_path, "0.2", "0.1")
    variant = _variant(
        tmp_path, locale="pt-BR", url="https://example.test/docs"
    )

    # Act
    links = not_found_version_links(variant)

    # Assert
    assert [link.href for link in links] == [
        "https://example.test/docs/0.2/pt-BR/index.html",
        "https://example.test/docs/0.1/pt-BR/index.html",
    ]


def test_not_found_version_links_empty_when_unversioned(
    tmp_path: Path,
) -> None:
    # Arrange
    variant = SiteVariant(
        site=Site(title="Site", description="", collections=()),
        output_path=tmp_path,
    )

    # Act / Assert
    assert not_found_version_links(variant) == ()
