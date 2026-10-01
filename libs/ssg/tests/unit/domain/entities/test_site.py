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
    assert navigation.sections[0].current_link_index == 1


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


def test_navigation_for_homepage_scopes_sections_to_given_collections(
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
    navigation = site.navigation_for(
        None, None, collections=(first_collection,)
    )

    # Assert
    assert [section.title for section in navigation.sections] == [
        "First Collection"
    ]
    assert navigation.sections[0].href == "first-collection/overview.html"


def test_navigation_for_reuses_collection_links_across_pages(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _collection_with_pages(
        tmp_path, "sample_collection", "Sample Collection"
    )
    site = Site(
        title="Learning Site", description="", collections=(collection,)
    )

    # Act
    first = site.navigation_for(collection, collection.pages[0])
    second = site.navigation_for(collection, collection.pages[1])

    # Assert
    assert first.sections[0].links is second.sections[0].links
    assert first.sections[0].current_link_index == 0
    assert second.sections[0].current_link_index == 1


def test_navigation_for_collection_without_page_marks_no_current_link(
    tmp_path: Path,
) -> None:
    # Arrange
    collection = _collection_with_pages(
        tmp_path, "sample_collection", "Sample Collection"
    )
    site = Site(
        title="Learning Site", description="", collections=(collection,)
    )

    # Act
    navigation = site.navigation_for(collection, None)

    # Assert
    assert navigation.sections[0].links == collection.navigation_links
    assert navigation.sections[0].current_link_index is None


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
