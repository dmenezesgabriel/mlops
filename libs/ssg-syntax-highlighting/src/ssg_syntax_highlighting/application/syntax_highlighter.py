import html
from html.parser import HTMLParser
from logging import getLogger
from typing import Protocol

from ssg.application.ports import HtmlPostProcessor
from ssg.domain import Site

LOGGER = getLogger(__name__)


class CodeSyntaxHighlighter(Protocol):
    def highlight(self, source: str, language: str) -> str: ...


class CodeSyntaxHighlighterFactory(Protocol):
    def create(self, style_name: str) -> CodeSyntaxHighlighter: ...


class CodeBlockSyntaxHighlightingProcessor(HtmlPostProcessor):
    def __init__(
        self,
        syntax_highlighter_factory: CodeSyntaxHighlighterFactory,
        default_style_name: str = "gruvbox-dark",
    ) -> None:
        self._syntax_highlighter_factory = syntax_highlighter_factory
        self._default_style_name = default_style_name
        self._highlighters: dict[str, CodeSyntaxHighlighter] = {}

    def process(self, rendered_html: str, site: Site) -> str:
        if "language-" not in rendered_html:
            return rendered_html

        style_name = site.extension_setting(
            "syntax_highlighting", "style", self._default_style_name
        )
        parser = CodeBlockHtmlParser(
            self._highlighter_for(style_name), self._copy_button_markup(site)
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

    # Highlighters are built once per style: constructing the pygments
    # formatter per page cost ~60% of a one-block page's render time.
    def _highlighter_for(self, style_name: str) -> CodeSyntaxHighlighter:
        if style_name not in self._highlighters:
            self._highlighters[style_name] = (
                self._syntax_highlighter_factory.create(style_name)
            )
        return self._highlighters[style_name]

    # The button is identical for every block on the page: labels resolve
    # once per process() call and the parser emits the markup verbatim.
    def _copy_button_markup(self, site: Site) -> str:
        tooltip = site.extension_setting(
            "i18n", "label_copy_code", "Copy to clipboard"
        )
        copied = site.extension_setting("i18n", "label_copied", "Copied!")
        return (
            '<button type="button" class="code-copy-button"'
            f' title="{html.escape(tooltip, quote=True)}"'
            f' aria-label="{html.escape(tooltip, quote=True)}"'
            f' data-copied-label="{html.escape(copied, quote=True)}">'
            "</button>"
        )


class CodeBlockHtmlParser(HTMLParser):
    def __init__(
        self,
        syntax_highlighter: CodeSyntaxHighlighter,
        copy_button_markup: str = "",
    ) -> None:
        # convert_charrefs=False keeps entity/char references raw so captured
        # code decodes exactly once (html.unescape in _append_highlighted_code)
        # and non-code references re-emit byte-faithful via the ref callbacks.
        super().__init__(convert_charrefs=False)
        self._syntax_highlighter = syntax_highlighter
        # Empty markup disables the copy-button feature: highlighted <pre>
        # blocks then re-emit byte-faithful with no frame wrapper.
        self._copy_button_markup = copy_button_markup
        self._fragments: list[str] = []
        self._code_fragments: list[str] = []
        self._pre_fragments: list[str] = []
        self._language: str | None = None
        self._inside_pre = False
        self._capturing_code = False
        self._pre_highlighted = False
        self.highlighted_blocks = 0

    def rendered_html(self) -> str:
        return "".join(self._fragments)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._capturing_code:
            self._code_fragments.append(self._start_tag_text(tag, attrs))
            return

        if tag == "pre":
            # The pre's own start tag belongs in its buffer so _flush_pre can
            # wrap buffer + button in the frame div.
            self._pre_fragments.append(self._start_tag_text(tag, attrs))
            self._inside_pre = True
            return

        self._append_fragment(self._start_tag_text(tag, attrs))
        language = self._language_from_attrs(attrs)
        if self._inside_pre and tag == "code" and language is not None:
            self._language = language
            self._capturing_code = True
            self._code_fragments = []

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        # Re-emit the raw `/>` form verbatim: the default splits into
        # start+end events, appending a phantom end tag that browsers reparse
        # as real markup (`<br/>` → `<br></br>` renders as two line breaks).
        start_tag_text = self.get_starttag_text()
        if start_tag_text is None:
            raise ValueError(
                "Missing start-tag text: handle_startendtag requires the "
                "parse loop to have populated raw tag text"
            )
        self.handle_data(start_tag_text)

    def handle_endtag(self, tag: str) -> None:
        if self._capturing_code and tag == "code":
            self._append_highlighted_code()
            self._pre_fragments.append("</code>")
            self._capturing_code = False
            self._language = None
            return

        if self._capturing_code:
            self._code_fragments.append(f"</{tag}>")
            return

        self._append_fragment(f"</{tag}>")
        if tag == "pre" and self._inside_pre:
            self._flush_pre()

    def handle_data(self, data: str) -> None:
        if self._capturing_code:
            self._code_fragments.append(data)
            return

        self._append_fragment(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.handle_data(f"&#{name};")

    # The base class drops comments, declarations, processing instructions and
    # unknown declarations entirely — this parser re-serializes full page
    # bodies, so each must re-emit verbatim instead of losing content.

    def handle_comment(self, data: str) -> None:
        self.handle_data(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.handle_data(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.handle_data(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self.handle_data(f"<![{data}]]>")

    def close(self) -> None:
        super().close()
        if self._capturing_code:
            # EOF inside <code> (malformed author HTML): flush the buffered
            # source verbatim rather than dropping it silently.
            self._pre_fragments.extend(self._code_fragments)
            self._code_fragments = []
            self._capturing_code = False
            self._language = None
        if self._inside_pre:
            # EOF inside <pre>: no completed capture, so byte-faithful flush
            # with no frame/button.
            self._flush_pre()

    def _append_fragment(self, fragment: str) -> None:
        if self._inside_pre:
            self._pre_fragments.append(fragment)
            return

        self._fragments.append(fragment)

    def _flush_pre(self) -> None:
        self._inside_pre = False
        wrapped = self._pre_highlighted and bool(self._copy_button_markup)
        if wrapped:
            self._fragments.append('<div class="code-frame">')
        self._fragments.extend(self._pre_fragments)
        if wrapped:
            self._fragments.append(self._copy_button_markup)
            self._fragments.append("</div>")
        self._pre_fragments = []
        self._pre_highlighted = False

    def _append_highlighted_code(self) -> None:
        source = html.unescape("".join(self._code_fragments))
        language = self._language
        if language is None:
            raise ValueError(
                "Missing code block language: expected language-* class"
            )

        self._pre_fragments.append(
            self._syntax_highlighter.highlight(source, language)
        )
        self._pre_highlighted = True
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
