from datetime import UTC, datetime
from pathlib import Path

from ssg.domain.entities.page import Page


def test_page_file_name() -> None:
    # Arrange
    page = Page(slug="intro", title="Intro", source_path=Path("intro.md"))

    # Act & Assert
    assert page.file_name() == "intro.html"


def test_page_normalizes_naive_date_to_utc() -> None:
    # Arrange
    page = Page(
        slug="post",
        title="Post",
        source_path=Path("post.md"),
        date=datetime(2026, 1, 15, 9, 30),
    )

    # Act & Assert
    assert page.date == datetime(2026, 1, 15, 9, 30, tzinfo=UTC)


def test_page_defaults_for_post_metadata() -> None:
    # Arrange / Act
    page = Page(slug="post", title="Post", source_path=Path("post.md"))

    # Assert
    assert page.date is None
    assert page.authors == ()
    assert page.draft is False
    assert page.pin is False
    assert page.readtime_minutes is None


def test_page_is_published_once_its_date_has_arrived() -> None:
    # Arrange
    page = Page(
        slug="post",
        title="Post",
        source_path=Path("post.md"),
        date=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
    )
    later = datetime(2026, 3, 1, tzinfo=UTC)

    # Act & Assert
    assert page.is_published(later) is True


def test_page_is_unpublished_when_draft_or_dated_in_the_future() -> None:
    # Arrange
    now = datetime(2026, 3, 1, tzinfo=UTC)
    draft = Page(
        slug="draft",
        title="Draft",
        source_path=Path("draft.md"),
        date=datetime(2026, 1, 15, tzinfo=UTC),
        draft=True,
    )
    future = Page(
        slug="future",
        title="Future",
        source_path=Path("future.md"),
        date=datetime(2026, 3, 2, tzinfo=UTC),
    )

    # Act & Assert
    assert draft.is_published(now) is False
    assert future.is_published(now) is False


def test_page_without_date_is_published() -> None:
    # Arrange
    page = Page(slug="undated", title="Undated", source_path=Path("u.md"))

    # Act & Assert
    assert page.is_published(datetime(2026, 3, 1, tzinfo=UTC)) is True
