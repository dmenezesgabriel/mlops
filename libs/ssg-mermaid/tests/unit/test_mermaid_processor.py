"""Unit tests for the Mermaid HTML post-processor and block parser."""

import pytest
from ssg_mermaid.application.mermaid_processor import (
    MermaidHtmlPostProcessor,
    MermaidRenderingError,
)


class FakeMermaidRenderer:
    def __init__(self) -> None:
        self.rendered_sources: list[str] = []
        self.fail = False

    def render(self, source: str) -> str:
        self.rendered_sources.append(source)
        if self.fail:
            raise MermaidRenderingError("fake render failure")
        return f'<svg data-source="{source}"></svg>'


def test_mermaid_fence_replaced_with_rendered_svg() -> None:
    # Arrange
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = '<pre><code class="language-mermaid">graph LR\n  A --&gt; B\n</code></pre>'

    # Act
    result = processor.process(html, None)

    # Assert — escaped HTML source is unescaped before reaching the renderer.
    assert renderer.rendered_sources == ["graph LR\n  A --> B\n"]
    assert '<div class="mermaid-diagram">' in result
    assert '<svg data-source="graph LR\n  A --> B\n"></svg>' in result
    assert "language-mermaid" not in result
    assert "<pre" not in result


def test_pre_class_mermaid_form_also_claimed() -> None:
    # Arrange — notebooks and hand-authored HTML may emit the material-style
    # `<pre class="mermaid">` shape rather than a language-* code class.
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = '<pre class="mermaid"><code>sequenceDiagram\n  A->>B: hi\n</code></pre>'

    # Act
    result = processor.process(html, None)

    # Assert
    assert renderer.rendered_sources == ["sequenceDiagram\n  A->>B: hi\n"]
    assert '<div class="mermaid-diagram">' in result
    assert "<pre" not in result


def test_non_mermaid_fence_passes_through_byte_faithfully() -> None:
    # Arrange
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = (
        '<pre><code class="language-python">def f():\n    pass\n</code></pre>'
    )

    # Act
    result = processor.process(html, None)

    # Assert
    assert result == html
    assert renderer.rendered_sources == []


def test_html_without_mermaid_returns_unchanged_and_skips_renderer() -> None:
    # Arrange — the hot path for the vast majority of pages must not pay
    # for parser work.
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = "<p>ordinary content &amp; <code>x</code></p>"

    # Act
    result = processor.process(html, None)

    # Assert
    assert result == html
    assert renderer.rendered_sources == []


def test_multiple_mermaid_blocks_each_rendered_in_order() -> None:
    # Arrange
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = (
        '<p>a</p><pre><code class="language-mermaid">graph A</code></pre>'
        '<p>b</p><pre><code class="language-mermaid">graph B</code></pre>'
    )

    # Act
    result = processor.process(html, None)

    # Assert
    assert renderer.rendered_sources == ["graph A", "graph B"]
    assert result.index("graph A") < result.index("graph B")
    assert result.count('class="mermaid-diagram"') == 2


def test_render_error_propagates() -> None:
    # Arrange
    renderer = FakeMermaidRenderer()
    renderer.fail = True
    processor = MermaidHtmlPostProcessor(renderer)
    html = '<pre><code class="language-mermaid">graph ???</code></pre>'

    # Act / Assert — a broken diagram fails the build loudly; silently
    # keeping the raw block would ship an unreadable page.
    with pytest.raises(MermaidRenderingError, match="fake render failure"):
        processor.process(html, None)


def test_same_source_rendered_once_across_process_calls() -> None:
    # Arrange — the same diagram may appear on a page and its locale
    # variants; a node subprocess per duplicate is wasted build time.
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = '<pre><code class="language-mermaid">graph LR</code></pre>'

    # Act
    first = processor.process(html, None)
    second = processor.process(html, None)

    # Assert
    assert renderer.rendered_sources == ["graph LR"]
    assert first == second


def test_markup_outside_pre_passes_through_byte_faithfully() -> None:
    # Arrange — one specimen per non-data event the parser must re-emit
    # verbatim: doctype, comment, entity/char refs, self-closing tag, pi,
    # CDATA, and a non-mermaid pre carrying attributes.
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = (
        "<!DOCTYPE html><p>a<!--note-->&amp;&#60;<br/></p>"
        "<?pi data?><![CDATA[x]]>"
        '<pre class="keep" id="y"><code class="language-go"><!--c-->a<br/>b</code></pre>'
        "<p>&copy;</p>"
        '<pre><code class="language-mermaid">graph LR</code></pre>'
    )

    # Act
    result = processor.process(html, None)

    # Assert — everything but the claimed block survives verbatim.
    assert result == (
        "<!DOCTYPE html><p>a<!--note-->&amp;&#60;<br/></p>"
        "<?pi data?><![CDATA[x]]>"
        '<pre class="keep" id="y"><code class="language-go"><!--c-->a<br/>b</code></pre>'
        "<p>&copy;</p>"
        '<div class="mermaid-diagram"><svg data-source="graph LR"></svg></div>'
    )
    assert renderer.rendered_sources == ["graph LR"]


def test_eof_inside_unclosed_pre_flushes_verbatim() -> None:
    # Arrange — a truncated document must not be rendered or dropped.
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = '<pre class="mermaid"><code>graph LR'

    # Act
    result = processor.process(html, None)

    # Assert
    assert result == html
    assert renderer.rendered_sources == []


def test_charref_inside_mermaid_source_unescaped_for_renderer() -> None:
    # Arrange
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = '<pre><code class="language-mermaid">graph LR&#10;A--&gt;B</code></pre>'

    # Act
    processor.process(html, None)

    # Assert
    assert renderer.rendered_sources == ["graph LR\nA-->B"]


def test_content_around_mermaid_block_preserved() -> None:
    # Arrange
    renderer = FakeMermaidRenderer()
    processor = MermaidHtmlPostProcessor(renderer)
    html = (
        "<h1>Title</h1>"
        '<pre><code class="language-mermaid">graph LR</code></pre>'
        '<pre><code class="language-python">x = 1</code></pre><p>after</p>'
    )

    # Act
    result = processor.process(html, None)

    # Assert
    assert result.startswith("<h1>Title</h1>")
    assert (
        '<pre><code class="language-python">x = 1</code></pre><p>after</p>'
        in result
    )
