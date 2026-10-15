"""HTML post-processor that renders ``mermaid`` fenced blocks to inline SVG."""

from collections.abc import Callable
from html import unescape
from html.parser import HTMLParser
from typing import Protocol

from ssg.application.ports import HtmlPostProcessor
from ssg.domain import Site


class MermaidRenderingError(RuntimeError):
    """Raised when Mermaid diagram rendering fails."""


class MermaidRenderer(Protocol):
    """Protocol for rendering Mermaid diagram sources to SVG."""

    def render(self, source: str) -> str:
        """Render a Mermaid diagram source to an SVG string.

        Example:
            >>> renderer.render("graph LR\\n  A --> B")
            '<svg ...>...</svg>'
        """
        ...


def _has_class(attrs: list[tuple[str, str | None]], name: str) -> bool:
    for key, value in attrs:
        if key == "class" and value and name in value.split():
            return True
    return False


class MermaidBlockHtmlParser(HTMLParser):
    """Swaps ``<pre>`` blocks carrying Mermaid sources for rendered SVG.

    Claims both emitted shapes: markdown-it's
    ``<pre><code class="language-mermaid">`` and material-style
    ``<pre class="mermaid">``. Non-mermaid content is re-emitted
    byte-faithfully so downstream processors see untouched markup.
    """

    def __init__(self, render_fn: Callable[[str], str]) -> None:
        super().__init__(convert_charrefs=False)
        self._render_fn = render_fn
        self._fragments: list[str] = []
        self._inside_pre = False
        self._is_mermaid_pre = False
        self._pre_fragments: list[str] = []
        self._source_fragments: list[str] = []

    def rendered_html(self) -> str:
        return "".join(self._fragments)

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if self._inside_pre:
            self._pre_fragments.append(self.get_starttag_text() or f"<{tag}>")
            if tag.lower() == "code" and _has_class(attrs, "language-mermaid"):
                self._is_mermaid_pre = True
            return
        if tag.lower() == "pre":
            self._inside_pre = True
            self._is_mermaid_pre = _has_class(attrs, "mermaid")
            self._pre_fragments = [self.get_starttag_text() or "<pre>"]
            self._source_fragments = []
            return
        self._fragments.append(self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        start_tag_text = self.get_starttag_text()
        if start_tag_text is None:
            raise ValueError(
                "Missing start-tag text: handle_startendtag requires the "
                "parse loop to have populated raw tag text"
            )
        if self._inside_pre:
            self._pre_fragments.append(start_tag_text)
            return
        self._fragments.append(start_tag_text)

    def handle_endtag(self, tag: str) -> None:
        if not self._inside_pre:
            self._fragments.append(f"</{tag}>")
            return
        if tag.lower() != "pre":
            self._pre_fragments.append(f"</{tag}>")
            return
        self._close_pre(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._inside_pre:
            self._pre_fragments.append(data)
            self._source_fragments.append(data)
            return
        self._fragments.append(data)

    def handle_comment(self, data: str) -> None:
        self._append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self._append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self._append(f"<![{data}]]>")

    def handle_entityref(self, name: str) -> None:
        # convert_charrefs=False: re-emit the raw `&name;` bytes so both
        # pass-through markup and captured sources stay verbatim — the
        # renderer gets the unescaped source from `unescape` at close.
        if self._inside_pre:
            raw = f"&{name};"
            self._pre_fragments.append(raw)
            self._source_fragments.append(raw)
            return
        self._fragments.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self._inside_pre:
            raw = f"&#{name};"
            self._pre_fragments.append(raw)
            self._source_fragments.append(raw)
            return
        self._fragments.append(f"&#{name};")

    def close(self) -> None:
        super().close()
        if self._inside_pre:
            # EOF inside an unclosed <pre>: re-emit verbatim rather than
            # rendering a truncated source.
            self._fragments.extend(self._pre_fragments)
            self._inside_pre = False

    def _append(self, text: str) -> None:
        if self._inside_pre:
            self._pre_fragments.append(text)
            return
        self._fragments.append(text)

    def _close_pre(self, end_tag: str) -> None:
        if self._is_mermaid_pre:
            source = unescape("".join(self._source_fragments))
            svg = self._render_fn(source)
            self._fragments.append(f'<div class="mermaid-diagram">{svg}</div>')
        else:
            self._pre_fragments.append(end_tag)
            self._fragments.extend(self._pre_fragments)
        self._inside_pre = False
        self._is_mermaid_pre = False


class MermaidHtmlPostProcessor(HtmlPostProcessor):
    """Post processor that replaces ``mermaid`` fenced blocks with inline SVG."""

    def __init__(self, renderer: MermaidRenderer) -> None:
        self.renderer = renderer
        self._cache: dict[str, str] = {}

    def process(self, rendered_html: str, site: Site) -> str:
        # Cheap gate: pages without the marker skip the parse pass.
        if "mermaid" not in rendered_html:
            return rendered_html

        parser = MermaidBlockHtmlParser(self._cached_render)
        parser.feed(rendered_html)
        parser.close()
        return parser.rendered_html()

    def _cached_render(self, source: str) -> str:
        # A node subprocess per unique diagram; identical sources on a
        # page and its locale variants share one render.
        if source in self._cache:
            return self._cache[source]

        rendered = self.renderer.render(source)
        self._cache[source] = rendered
        return rendered
