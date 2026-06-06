import html
from html.parser import HTMLParser
from logging import getLogger
from typing import Protocol

from ssg.application.ports import HtmlPostProcessor
from ssg.domain.site import Site

LOGGER = getLogger(__name__)


class CodeSyntaxHighlighter(Protocol):
    def highlight(self, source: str, language: str) -> str:
        pass


class CodeSyntaxHighlighterFactory(Protocol):
    def create(self, style_name: str) -> CodeSyntaxHighlighter:
        pass


class CodeBlockSyntaxHighlightingProcessor(HtmlPostProcessor):
    def __init__(
        self,
        syntax_highlighter_factory: CodeSyntaxHighlighterFactory,
        default_style_name: str = "gruvbox-dark",
    ) -> None:
        self._syntax_highlighter_factory = syntax_highlighter_factory
        self._default_style_name = default_style_name

    def process(self, rendered_html: str, site: Site) -> str:
        if "language-" not in rendered_html:
            return rendered_html

        style_name = site.extension_setting(
            "syntax_highlighting", "style", self._default_style_name
        )
        parser = CodeBlockHtmlParser(
            self._syntax_highlighter_factory.create(style_name)
        )
        parser.feed(rendered_html)
        parser.close()
        LOGGER.info(
            "syntax_highlighting_finished",
            extra={
                "context": {
                    "highlighted_blocks": parser.highlighted_blocks,
                    "style": style_name,
                }
            },
        )
        return parser.rendered_html()


class CodeBlockHtmlParser(HTMLParser):
    def __init__(self, syntax_highlighter: CodeSyntaxHighlighter) -> None:
        super().__init__(convert_charrefs=True)
        self._syntax_highlighter = syntax_highlighter
        self._fragments: list[str] = []
        self._code_fragments: list[str] = []
        self._language: str | None = None
        self._inside_pre = False
        self._capturing_code = False
        self.highlighted_blocks = 0

    def rendered_html(self) -> str:
        return "".join(self._fragments)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._capturing_code:
            self._code_fragments.append(self._start_tag_text(tag, attrs))
            return

        self._fragments.append(self._start_tag_text(tag, attrs))
        if tag == "pre":
            self._inside_pre = True
            return

        language = self._language_from_attrs(attrs)
        if self._inside_pre and tag == "code" and language is not None:
            self._language = language
            self._capturing_code = True
            self._code_fragments = []

    def handle_endtag(self, tag: str) -> None:
        if self._capturing_code and tag == "code":
            self._append_highlighted_code()
            self._fragments.append("</code>")
            self._capturing_code = False
            self._language = None
            return

        if self._capturing_code:
            self._code_fragments.append(f"</{tag}>")
            return

        self._fragments.append(f"</{tag}>")
        if tag == "pre":
            self._inside_pre = False

    def handle_data(self, data: str) -> None:
        if self._capturing_code:
            self._code_fragments.append(data)
            return

        self._fragments.append(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    def _append_highlighted_code(self) -> None:
        source = html.unescape("".join(self._code_fragments))
        language = self._language
        if language is None:
            raise ValueError(
                "Missing code block language: expected language-* class"
            )

        self._fragments.append(
            self._syntax_highlighter.highlight(source, language)
        )
        self.highlighted_blocks += 1

    def _language_from_attrs(
        self, attrs: list[tuple[str, str | None]]
    ) -> str | None:
        for name, value in attrs:
            if name == "class" and value is not None:
                return self._language_from_class(value)

        return None

    def _language_from_class(self, class_value: str) -> str | None:
        for class_name in class_value.split():
            if class_name.startswith("language-") and len(class_name) > len(
                "language-"
            ):
                return class_name.removeprefix("language-")

        return None

    def _start_tag_text(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> str:
        rendered_attrs = "".join(
            self._render_attribute(name, value) for name, value in attrs
        )
        return f"<{tag}{rendered_attrs}>"

    def _render_attribute(self, name: str, value: str | None) -> str:
        if value is None:
            return f" {name}"

        return f' {name}="{html.escape(value, quote=True)}"'
