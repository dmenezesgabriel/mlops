from datetime import UTC, datetime
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


def test_page_index_returns_position_for_known_slug(tmp_path: Path) -> None:
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
            Page(
                slug="details",
                title="Details",
                source_path=tmp_path / "details.md",
            ),
        ),
        videos={},
    )

    # Act / Assert
    assert collection.page_index("details") == 1


def test_page_href_rejects_unknown_slug(tmp_path: Path) -> None:
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

    # Act / Assert
    with pytest.raises(ValueError, match="expected one of"):
        collection.page_href("missing")


def test_first_page_rejects_empty_collection(tmp_path: Path) -> None:
    # Arrange — config load rejects empty collections, but a directly
    # constructed one can still reach root_href() (index nav card).
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )

    # Act / Assert
    with pytest.raises(ValueError, match="expected at least one page"):
        collection.first_page()


def test_page_index_rejects_unknown_slug(tmp_path: Path) -> None:
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

    # Act / Assert
    with pytest.raises(ValueError, match="expected one of"):
        collection.page_index("missing")


def _posts_page(
    slug: str, source_root: Path, date: datetime | None, draft: bool = False
) -> Page:
    return Page(
        slug=slug,
        title=slug.title(),
        source_path=source_root / f"{slug}.md",
        date=date,
        draft=draft,
    )


def _posts_collection(
    tmp_path: Path, pages: tuple[Page, ...]
) -> ContentCollection:
    return ContentCollection(
        name="blog",
        title="Blog",
        source_root=tmp_path,
        output_slug="blog",
        pages=pages,
        videos={},
        kind="posts",
    )


def test_published_drops_draft_and_future_dated_posts(tmp_path: Path) -> None:
    # Arrange
    now = datetime(2026, 3, 1, tzinfo=UTC)
    collection = _posts_collection(
        tmp_path,
        (
            _posts_page("intro", tmp_path, datetime(2026, 2, 1, tzinfo=UTC)),
            _posts_page("future", tmp_path, datetime(2026, 3, 2, tzinfo=UTC)),
            _posts_page(
                "draft", tmp_path, datetime(2026, 1, 1, tzinfo=UTC), draft=True
            ),
        ),
    )

    # Act
    published = collection.published(now)

    # Assert
    assert tuple(page.slug for page in published.pages) == ("intro",)
    assert published.name == collection.name
    assert published.kind == "posts"
    # The published view is also a usable navigation source.
    assert published.page_index("intro") == 0


def test_published_keeps_every_page_of_a_plain_collection(
    tmp_path: Path,
) -> None:
    # Arrange — draft/date only gate dated-posts collections.
    now = datetime(2026, 3, 1, tzinfo=UTC)
    page = _posts_page(
        "draft", tmp_path, datetime(2026, 1, 1, tzinfo=UTC), draft=True
    )
    collection = ContentCollection(
        name="docs",
        title="Docs",
        source_root=tmp_path,
        output_slug="docs",
        pages=(page,),
        videos={},
    )

    # Act & Assert
    assert collection.published(now) is collection


def test_root_href_falls_back_to_the_index_for_an_empty_collection(
    tmp_path: Path,
) -> None:
    # Arrange — a blog whose every post is still a draft publishes no pages
    # but still owns its index URL.
    collection = _posts_collection(tmp_path, ())

    # Act & Assert
    assert collection.root_href() == "blog/index.html"
