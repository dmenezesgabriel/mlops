from pathlib import Path

import pytest
from ssg.domain.entities.content_collection import ContentCollection
from ssg.domain.entities.page import Page


def test_source_file_rejects_paths_outside_collection_root(
    tmp_path: Path,
) -> None:
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
        pages=(
            Page(
                slug="overview",
                title="Overview",
                source_path=tmp_path / "README.md",
            ),
        ),
        videos={},
    )

    # Act
    href = collection.page_href("overview")

    # Assert
    assert href == "overview.html"


def test_collection_previous_and_next_page_follow_configured_order(
    tmp_path: Path,
) -> None:
    # Arrange
    first_page = Page(
        slug="overview", title="Overview", source_path=tmp_path / "README.md"
    )
    second_page = Page(
        slug="details", title="Details", source_path=tmp_path / "details.md"
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(first_page, second_page),
        videos={},
    )

    # Act / Assert
    assert collection.previous_page(second_page) == first_page
    assert collection.next_page(first_page) == second_page
    assert collection.previous_page(first_page) is None
    assert collection.next_page(second_page) is None
