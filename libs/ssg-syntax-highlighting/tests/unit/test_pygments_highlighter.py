import pytest
from ssg_syntax_highlighting.infrastructure.pygments_highlighter import (
    PygmentsCodeSyntaxHighlighterFactory,
)


def test_create_rejects_unknown_style_naming_the_setting() -> None:
    # Arrange
    factory = PygmentsCodeSyntaxHighlighterFactory()

    # Act / Assert
    with pytest.raises(ValueError, match="syntax_highlighting") as exc_info:
        factory.create("bogus-style")

    assert "bogus-style" in str(exc_info.value)
