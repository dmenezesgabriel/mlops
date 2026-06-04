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
    assert collection.source_root == collection_root.resolve()
    assert collection.pages[0].source_path == collection_root.resolve() / "README.md"
    assert collection.videos["demo"] == (site_path / "../videos/demo.mp4").resolve()


def test_load_rejects_non_mapping_config(tmp_path: Path) -> None:
    # Arrange
    config_path = tmp_path / "site.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    # Act / Assert
    with pytest.raises(ValueError, match="expected YAML mapping"):
        SiteConfigRepository().load(config_path)
