from pathlib import Path

from ssg.domain.entities.page import Page


def test_page_file_name() -> None:
    # Arrange
    page = Page(slug="intro", title="Intro", source_path=Path("intro.md"))

    # Act & Assert
    assert page.file_name() == "intro.html"
