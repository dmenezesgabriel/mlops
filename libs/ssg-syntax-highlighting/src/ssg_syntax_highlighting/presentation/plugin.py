from ssg.application.ports import HtmlPostProcessor

from ssg_syntax_highlighting.application.syntax_highlighter import (
    CodeBlockSyntaxHighlightingProcessor,
)
from ssg_syntax_highlighting.infrastructure.pygments_highlighter import (
    PygmentsCodeSyntaxHighlighterFactory,
)


def create_pygments_html_post_processor() -> HtmlPostProcessor:
    return CodeBlockSyntaxHighlightingProcessor(PygmentsCodeSyntaxHighlighterFactory())
