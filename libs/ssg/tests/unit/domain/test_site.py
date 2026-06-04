from pathlib import Path

import pytest
from ssg.domain.site import ContentCollection, Page, Site


def test_source_file_rejects_paths_outside_collection_root(tmp_path: Path) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected path under"):
        collection.source_file("../outside.py")


def test_page_href_returns_html_path_for_known_page(tmp_path: Path) -> None:
    # Arrange
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(Page(slug="overview", title="Overview", source_path=tmp_path / "README.md"),),
        videos={},
    )

    # Act
    href = collection.page_href("overview")

    # Assert
    assert href == "overview.html"


def test_site_selected_collections_reports_expected_names(tmp_path: Path) -> None:
    # Arrange
    site = Site(
        title="Learning Site",
        description="",
        collections=(
            ContentCollection(
                name="sample_collection",
                title="Sample Collection",
                source_root=tmp_path,
                output_slug="sample-collection",
                pages=(),
                videos={},
            ),
        ),
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected one of"):
        site.selected_collections("missing_collection")
