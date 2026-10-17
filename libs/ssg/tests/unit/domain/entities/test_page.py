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
