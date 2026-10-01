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
