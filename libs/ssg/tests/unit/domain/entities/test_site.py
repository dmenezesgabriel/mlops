from pathlib import Path

import pytest
from ssg.domain.entities.content_collection import ContentCollection
from ssg.domain.entities.page import Page
from ssg.domain.entities.site import Site


def test_site_selected_collections_reports_expected_names(
    tmp_path: Path,
) -> None:
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


def test_navigation_for_page_marks_current_page_and_links_from_collection_page(
    tmp_path: Path,
) -> None:
    # Arrange
    overview = Page(
        slug="overview", title="Overview", source_path=tmp_path / "README.md"
    )
    details = Page(
        slug="details", title="Details", source_path=tmp_path / "details.md"
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(overview, details),
        videos={},
    )
    site = Site(
        title="Learning Site", description="", collections=(collection,)
    )

    # Act
    navigation = site.navigation_for(collection, details)

    # Assert
    assert navigation.home_href == "../index.html"
    assert navigation.sections[0].href == "../sample-collection/overview.html"
    assert navigation.sections[0].links[1].current is True
    assert navigation.sections[0].links[1].aria_current() == "page"


def test_navigation_for_homepage_lists_projects_without_article_links(
    tmp_path: Path,
) -> None:
    # Arrange
    first_collection = _collection_with_pages(
        tmp_path, "first_collection", "First Collection"
    )
    second_collection = _collection_with_pages(
        tmp_path, "second_collection", "Second Collection"
    )
    site = Site(
        title="Learning Site",
        description="",
        collections=(first_collection, second_collection),
    )

    # Act
    navigation = site.navigation_for(None, None)

    # Assert
    assert navigation.home_href == "index.html"
    assert [section.title for section in navigation.sections] == [
        "First Collection",
        "Second Collection",
    ]
    assert navigation.sections[0].href == "first-collection/overview.html"
    assert navigation.sections[0].links == ()
    assert navigation.sections[1].links == ()


def _collection_with_pages(
    tmp_path: Path,
    name: str,
    title: str,
) -> ContentCollection:
    overview = Page(
        slug="overview",
        title="Overview",
        source_path=tmp_path / name / "README.md",
    )
    details = Page(
        slug="details",
        title="Details",
        source_path=tmp_path / name / "details.md",
    )
    return ContentCollection(
        name=name,
        title=title,
        source_root=tmp_path / name,
        output_slug=name.replace("_", "-"),
        pages=(overview, details),
        videos={},
    )
