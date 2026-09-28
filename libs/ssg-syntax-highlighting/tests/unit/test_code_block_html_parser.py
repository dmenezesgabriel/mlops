"""Tag-level edge paths for ``CodeBlockHtmlParser``.

``test_syntax_highlighting.py`` covers ``process()`` end to end; these tests
drive the parser directly so branches that only appear mid-stream (markup
nested inside a code capture, entities inside ``<script>``/``<style>``, and
attribute shapes that never yield a language) can be asserted exactly.
"""

import pytest
from ssg_syntax_highlighting.application.syntax_highlighter import (
    CodeBlockHtmlParser,
)


class RecordingHighlighter:
    """Captures (source, language) instead of producing markup."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def highlight(self, source: str, language: str) -> str:
        self.calls.append((source, language))
        return f"<hl>{source}</hl>"


def parse(
    html_text: str,
) -> tuple[str, RecordingHighlighter]:
    highlighter = RecordingHighlighter()
    parser = CodeBlockHtmlParser(highlighter)
    parser.feed(html_text)
    parser.close()
    return parser.rendered_html(), highlighter


def test_nested_markup_inside_code_is_highlighted_as_source() -> None:
    # Arrange
    html_text = '<pre><code class="language-python">x <b>y</b> z</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert highlighter.calls == [("x <b>y</b> z", "python")]
    assert rendered == (
        '<pre><code class="language-python"><hl>x <b>y</b> z</hl></code></pre>'
    )


def test_text_outside_code_capture_passes_through() -> None:
    # Arrange
    html_text = '<p>intro</p><pre><code class="language-python">x</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert rendered.startswith("<p>intro</p>")
    assert highlighter.calls == [("x", "python")]


def test_entities_inside_script_pass_through_verbatim() -> None:
    # convert_charrefs skips <script>/<style> content: raw reference text
    # arrives via handle_data instead of the entityref/charref callbacks.
    # Arrange
    html_text = "<script>a &amp; b &#60; c</script>"

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_reference_callbacks_reemit_verbatim_when_not_converted() -> None:
    # handle_entityref/handle_charref are dead paths under
    # convert_charrefs=True; they exist so a future convert_charrefs=False
    # parser keeps references verbatim instead of dropping them (the base
    # class is a no-op). Pin that forwarding contract directly.
    parser = CodeBlockHtmlParser(RecordingHighlighter())

    # Act
    parser.handle_entityref("amp")
    parser.handle_charref("60")

    # Assert
    assert parser.rendered_html() == "&amp;&#60;"


def test_code_without_language_class_passes_through() -> None:
    # Arrange
    html_text = '<pre><code class="foo bar">x</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert rendered == html_text
    assert highlighter.calls == []


def test_valueless_attribute_is_reemitted_bare() -> None:
    # Arrange
    html_text = (
        '<p hidden>intro</p><pre><code class="language-python">x</code></pre>'
    )

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered.startswith("<p hidden>intro</p>")


def test_closing_code_without_language_raises() -> None:
    # Arrange: _capturing_code always pairs with a language in feed() paths;
    # the raise guards the invariant if state is ever decoupled.
    parser = CodeBlockHtmlParser(RecordingHighlighter())
    parser._capturing_code = True

    # Act / Assert
    with pytest.raises(ValueError, match="Missing code block language"):
        parser.feed("</code>")
