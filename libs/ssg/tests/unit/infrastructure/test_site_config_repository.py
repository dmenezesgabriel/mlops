from pathlib import Path

import pytest
from ssg.infrastructure.site_config_repository import SiteConfigRepository


def test_load_reads_generic_site_manifest(tmp_path: Path) -> None:
    # Arrange
    site_path = tmp_path / "site"
    collection_root = tmp_path / "content" / "sample_collection"
    site_path.mkdir()
    collection_root.mkdir(parents=True)
    config_path = site_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "  description: Rendered content collections.\n"
        "extensions:\n"
        "  syntax_highlighting:\n"
        "    style: monokai\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    output_slug: sample\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        "      videos:\n"
        "        demo: ../videos/demo.mp4\n",
        encoding="utf-8",
    )
    repository = SiteConfigRepository()

    # Act
    site = repository.load(config_path)

    # Assert
    collection = site.collections[0]
    assert site.title == "Learning Site"
    assert collection.name == "sample_collection"
    assert (
        site.extension_setting("syntax_highlighting", "style", "gruvbox-dark")
        == "monokai"
    )
    assert collection.source_root == collection_root.resolve()
    assert (
        collection.pages[0].source_path
        == collection_root.resolve() / "README.md"
    )
    assert (
        collection.videos["demo"]
        == (site_path / "../videos/demo.mp4").resolve()
    )


def test_load_rejects_duplicate_page_slugs(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    pages:\n"
        "      - slug: dup\n"
        "        title: First\n"
        "        source: first.md\n"
        "      - slug: dup\n"
        "        title: Second\n"
        "        source: second.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="duplicate page slug 'dup'"):
        SiteConfigRepository().load(config_path)


@pytest.mark.parametrize(
    "slug",
    ["../escaped", "..", "a/b", "dot.slug", "has space", "Upper", ""],
)
def test_load_rejects_page_slugs_outside_charset(
    tmp_path: Path, slug: str
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    pages:\n"
        f'      - slug: "{slug}"\n'
        "        title: Page\n"
        "        source: page.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid page slug"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_duplicate_collection_names(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: same_name\n"
        "    title: First Collection\n"
        "    source_root: ../content/first\n"
        "    output_slug: first\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: overview.md\n"
        "  - name: same_name\n"
        "    title: Second Collection\n"
        "    source_root: ../content/second\n"
        "    output_slug: second\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: overview.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(
        ValueError, match="duplicate collection name 'same_name'"
    ):
        SiteConfigRepository().load(config_path)


def test_load_rejects_duplicate_collection_output_slugs(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: first_collection\n"
        "    title: First Collection\n"
        "    source_root: ../content/first\n"
        "    output_slug: same\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: overview.md\n"
        "  - name: second_collection\n"
        "    title: Second Collection\n"
        "    source_root: ../content/second\n"
        "    output_slug: same\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: overview.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(
        ValueError, match="duplicate collection output_slug 'same'"
    ):
        SiteConfigRepository().load(config_path)


@pytest.mark.parametrize("output_slug", ["../escaped", "a/b", "Upper"])
def test_load_rejects_collection_output_slugs_outside_charset(
    tmp_path: Path, output_slug: str
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        f'    output_slug: "{output_slug}"\n'
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: overview.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid collection output_slug"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_collection_with_no_pages(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: empty_collection\n"
        "    title: Empty Collection\n"
        "    source_root: ../content/empty_collection\n"
        "    pages: []\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected at least one page"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_non_mapping_config(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="expected YAML mapping"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_non_string_extension_setting(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "extensions:\n"
        "  syntax_highlighting:\n"
        "    style: 42\n"
        "collections: []\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(
        ValueError,
        match="expected extension setting syntax_highlighting.style string",
    ):
        SiteConfigRepository().load(config_path)


@pytest.mark.parametrize("asset_key", ["videos", "images"])
def test_load_rejects_non_string_asset_names(
    tmp_path: Path, asset_key: str
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        f"      {asset_key}:\n"
        "        1: first.mp4\n"
        '        "1": second.mp4\n',
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected string key"):
        SiteConfigRepository().load(config_path)


@pytest.mark.parametrize("asset_key", ["videos", "images"])
def test_load_rejects_non_string_asset_paths(
    tmp_path: Path, asset_key: str
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        f"      {asset_key}:\n"
        "        demo: 42\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected demo path string"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_non_string_description(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "  description: 42\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected description string"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_non_string_collection_output_slug(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    output_slug: 123\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected output_slug string"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_non_string_extension_names(tmp_path: Path) -> None:
    # Arrange — YAML-1.1 parses the bare key `on` as boolean True.
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "extensions:\n"
        "  on:\n"
        "    style: monokai\n"
        "collections: []\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected string key"):
        SiteConfigRepository().load(config_path)


def test_load_rejects_non_string_extension_setting_names(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "extensions:\n"
        "  syntax_highlighting:\n"
        "    1: monokai\n"
        "collections: []\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected string key"):
        SiteConfigRepository().load(config_path)


@pytest.mark.parametrize("source", ["../secret.md", "../../escaped.md"])
def test_load_rejects_page_source_outside_source_root(
    tmp_path: Path, source: str
) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: content\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        f'        source: "{source}"\n',
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid page source"):
        SiteConfigRepository().load(config_path)


def test_load_resolves_page_source_within_source_root(
    tmp_path: Path,
) -> None:
    # Arrange — `..` segments that stay inside source_root are allowed and
    # normalized, matching ContentCollection.source_file() semantics.
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: content\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: sub/../page.md\n",
        encoding="utf-8",
    )

    # Act
    site = SiteConfigRepository().load(config_path)

    # Assert
    page = site.collections[0].pages[0]
    assert page.source_path == (tmp_path / "content" / "page.md").resolve()


def test_load_resolves_absolute_configured_paths(tmp_path: Path) -> None:
    # Arrange — absolute configured paths normalize `..` just like the
    # config-relative branch.
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        f"    source_root: {tmp_path}/a/../b\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        "      videos:\n"
        f"        demo: {tmp_path}/v/../w.mp4\n",
        encoding="utf-8",
    )

    # Act
    site = SiteConfigRepository().load(config_path)

    # Assert
    collection = site.collections[0]
    assert collection.source_root == (tmp_path / "b").resolve()
    assert collection.videos["demo"] == (tmp_path / "w.mp4").resolve()


@pytest.mark.parametrize("asset_key", ["videos", "images"])
def test_load_rejects_duplicate_asset_basenames(
    tmp_path: Path, asset_key: str
) -> None:
    # Arrange — configured assets flatten into one output dir per kind
    # (assets/<kind>/demo.ext), so a shared basename silently overwrites at
    # render; reject it at load instead.
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: content\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        f"      {asset_key}:\n"
        "        first: va/demo.ext\n"
        "        second: vb/demo.ext\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(
        ValueError, match="duplicate asset filename 'demo.ext'"
    ):
        SiteConfigRepository().load(config_path)


def test_load_rejects_case_folded_asset_basenames(tmp_path: Path) -> None:
    # Arrange — `Demo.ext`/`demo.ext` write the same output path on
    # case-insensitive filesystems, so the check compares case-folded.
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: content\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        "      videos:\n"
        "        first: va/Demo.ext\n"
        "        second: vb/demo.ext\n",
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(
        ValueError, match="duplicate asset filename 'demo.ext'"
    ):
        SiteConfigRepository().load(config_path)


def test_load_allows_same_basename_across_asset_kinds(tmp_path: Path) -> None:
    # Arrange — videos and images write to different output dirs
    # (assets/videos/ vs assets/images/), so a shared basename is not a
    # collision.
    config_path = tmp_path / "site.yaml"
    config_path.write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: content\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "    assets:\n"
        "      videos:\n"
        "        clip: va/demo.ext\n"
        "      images:\n"
        "        diagram: vb/demo.ext\n",
        encoding="utf-8",
    )

    # Act
    site = SiteConfigRepository().load(config_path)

    # Assert
    collection = site.collections[0]
    assert collection.videos["clip"].name == "demo.ext"
    assert collection.images["diagram"].name == "demo.ext"
