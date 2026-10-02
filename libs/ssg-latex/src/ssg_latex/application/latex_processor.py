import re
from collections.abc import Callable
from html import unescape
from html.parser import HTMLParser
from typing import Protocol

from ssg.application.ports import HtmlPostProcessor
from ssg.domain import Site

# Regular expression matching display math ($$.*$$) or inline math ($...$)
# - Display math: matches anything enclosed between double dollar signs non-greedily.
# - Inline math: matches anything enclosed between single dollar signs non-greedily,
#   ensuring the boundaries are non-whitespace, and not preceded by $ (avoiding display math)
#   or followed by a digit (avoiding currency ranges/values like $10-$20).
MATH_PATTERN = re.compile(
    r"(\$\$.*?\$\$|(?<!\$)\$[^\$\s](?:[^\$]*?[^\$\s])?\$(?!\d))", re.DOTALL
)

SELF_CLOSING_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def _escape_text_underscores(expression: str) -> str:
    """Escape underscores inside \\text{...} blocks to protect them from markdown parsing side-effects."""

    def replace_match(match: re.Match[str]) -> str:
        content = match.group(1)
        # Only replace underscores not already preceded by a backslash
        escaped_content = re.sub(r"(?<!\\)_", r"\\_", content)
        return f"\\text{{{escaped_content}}}"

    # \text{} bodies can nest one brace level (a_{b}); the inner-group
    # alternative keeps them matchable. Two-plus levels stay unmatched and
    # reach KaTeX raw — it reports a named ParseError for those.
    return re.sub(
        r"\\text\{((?:[^{}]|\{[^{}]*\})*)\}", replace_match, expression
    )


class LatexRenderingError(RuntimeError):
    """Raised when KaTeX/LaTeX compilation fails."""


class LatexRenderer(Protocol):
    """Protocol for rendering LaTeX math expressions to HTML."""

    def render(self, expression: str, display_mode: bool) -> str:
        """Render a LaTeX expression to HTML."""
        ...


class LatexHtmlParser(HTMLParser):
    """HTML parser that extracts and renders LaTeX expressions in text nodes."""

    def __init__(self, render_fn: Callable[[str, bool], str]) -> None:
        super().__init__(convert_charrefs=False)
        self._render_fn = render_fn
        self._fragments: list[str] = []
        self._tag_stack: list[str] = []
        self._pending_text: list[str] = []
        self.math_rendered = False

    def rendered_html(self) -> str:
        return "".join(self._fragments)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self._flush_text()
        tag_lower = tag.lower()
        if tag_lower not in SELF_CLOSING_TAGS:
            self._tag_stack.append(tag_lower)
        self._fragments.append(self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        # Re-emit the raw `/>` form verbatim: the default splits into
        # start+end events, and handle_endtag appends a phantom `</tag>`
        # browsers reparse as real markup (`<br/>` -> `<br></br>` doubles
        # a line break). Self-closed tags enclose nothing, so no stack push.
        self._flush_text()
        start_tag_text = self.get_starttag_text()
        if start_tag_text is None:
            raise ValueError(
                "Missing start-tag text: handle_startendtag requires the "
                "parse loop to have populated raw tag text"
            )
        self._fragments.append(start_tag_text)

    def handle_endtag(self, tag: str) -> None:
        # Flush before popping so enclosed text is classified with the
        # enclosing tag still on the stack.
        self._flush_text()
        tag_lower = tag.lower()
        if tag_lower in self._tag_stack:
            while self._tag_stack:
                popped = self._tag_stack.pop()
                if popped == tag_lower:
                    break
        self._fragments.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self._pending_text.append(data)

    def handle_comment(self, data: str) -> None:
        self._flush_text()
        self._fragments.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._flush_text()
        self._fragments.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self._flush_text()
        self._fragments.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        # The base class drops `<![...]]>` sections (e.g. CDATA) entirely;
        # this parser re-serializes page bodies, so re-emit verbatim.
        self._flush_text()
        self._fragments.append(f"<![{data}]]>")

    def handle_entityref(self, name: str) -> None:
        self._pending_text.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._pending_text.append(f"&#{name};")

    def close(self) -> None:
        super().close()
        self._flush_text()

    def _flush_text(self) -> None:
        """Split one contiguous text run for math, then emit it.

        convert_charrefs=False fires entityref/charref between data chunks,
        so a formula like ``$a &lt; b$`` arrives split across events. Buffering
        the verbatim bytes rejoins the run for MATH_PATTERN while keeping
        non-math entities (and ``&#36;``) byte-for-byte; only the extracted
        expression is unescaped for KaTeX.
        """
        if not self._pending_text:
            return
        data = "".join(self._pending_text)
        self._pending_text.clear()

        ignored_tags = {"pre", "code", "script", "style", "textarea"}
        if any(t in ignored_tags for t in self._tag_stack):
            self._fragments.append(data)
            return

        parts = MATH_PATTERN.split(data)
        for i in range(len(parts)):
            if i % 2 == 1:
                # Math block matched
                self.math_rendered = True
                match = parts[i]
                if match.startswith("$$") and match.endswith("$$"):
                    expr = unescape(match[2:-2]).strip()
                    expr = _escape_text_underscores(expr)
                    parts[i] = self._render_fn(expr, True)
                else:
                    expr = unescape(match[1:-1]).strip()
                    expr = _escape_text_underscores(expr)
                    parts[i] = self._render_fn(expr, False)
        self._fragments.append("".join(parts))


class LatexHtmlPostProcessor(HtmlPostProcessor):
    """Post processor that translates LaTeX formulas in pages into KaTeX elements."""

    def __init__(self, renderer: LatexRenderer) -> None:
        self.renderer = renderer
        self._cache: dict[tuple[str, bool], str] = {}

    def process(self, rendered_html: str, site: Site) -> str:
        parser = LatexHtmlParser(self._cached_render)
        parser.feed(rendered_html)
        parser.close()

        processed_html = parser.rendered_html()

        if parser.math_rendered:
            css_url = site.extension_setting(
                "latex",
                "katex_css_url",
                "https://cdn.jsdelivr.net/npm/katex@0.17.0/dist/katex.min.css",
            )
            css_link = f'<link rel="stylesheet" href="{css_url}">'
            # process() only ever sees a page-body fragment — the page
            # template adds <head> later, so there is no head seam to
            # inject into. Prepending puts the body-ok link at the head of
            # the article body: the browser fetches the stylesheet at the
            # start of body parse instead of after the article tail.
            processed_html = f"{css_link}{processed_html}"

        return processed_html

    def _cached_render(self, expression: str, display_mode: bool) -> str:
        cache_key = (expression, display_mode)
        if cache_key in self._cache:
            return self._cache[cache_key]

        rendered = self.renderer.render(expression, display_mode)
        self._cache[cache_key] = rendered
        return rendered
