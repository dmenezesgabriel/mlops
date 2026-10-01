# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false
# types-pygments does not cover pygments.lexers.special and leaves get_lexer_by_name
# partially untyped; both boundaries are cast/annotated at our call sites below.
from logging import getLogger

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name
from pygments.lexers.special import TextLexer
from pygments.util import ClassNotFound

from ssg_syntax_highlighting.application.syntax_highlighter import (
    CodeSyntaxHighlighter,
)

LOGGER = getLogger(__name__)


class PygmentsCodeSyntaxHighlighter(CodeSyntaxHighlighter):
    def __init__(self, style_name: str) -> None:
        self._style_name = style_name
        try:
            self._formatter: HtmlFormatter[str] = HtmlFormatter(
                nowrap=True, noclasses=True, style=style_name
            )
        except ClassNotFound as exc:
            raise ValueError(
                f"Invalid syntax_highlighting.style {style_name!r}: "
                f"expected a Pygments style name ({exc})"
            ) from exc

    def highlight(self, source: str, language: str) -> str:
        lexer = self._lexer_for_language(language)
        highlighted_source = highlight(source, lexer, self._formatter)
        return highlighted_source.replace(
            "<span ", '<span class="highlight-token" '
        )

    def _lexer_for_language(self, language: str) -> Lexer:
        try:
            lexer = get_lexer_by_name(language)
            LOGGER.info(
                "syntax_highlighting_language_selected",
                extra={
                    "context": {
                        "language": language,
                        "style": self._style_name,
                    }
                },
            )
            return lexer
        except ClassNotFound:
            LOGGER.info(
                "syntax_highlighting_language_fallback",
                extra={"context": {"language": language, "fallback": "text"}},
            )
            return TextLexer()


class PygmentsCodeSyntaxHighlighterFactory:
    def create(self, style_name: str) -> PygmentsCodeSyntaxHighlighter:
        return PygmentsCodeSyntaxHighlighter(style_name)
