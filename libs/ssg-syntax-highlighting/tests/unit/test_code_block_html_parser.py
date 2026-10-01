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
    # convert_charrefs=False routes entity/char references through these
    # callbacks; they re-emit verbatim so non-code references stay
    # byte-faithful and captured code decodes exactly once via unescape.
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


def test_self_closing_tags_reemit_verbatim() -> None:
    # Arrange — the default handle_startendtag splits into start+end events,
    # emitting a phantom end tag (`<br/>`→`<br></br>`) that browsers reparse
    # as real markup (a stray `</br>` renders as a second line break).
    html_text = '<p>a<br/>b</p><hr/><img src="a.png"/><input/>'

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_self_closing_tag_inside_code_is_highlighted_source() -> None:
    # Arrange — markup inside a code capture is source text (pinned contract);
    # the authored `/>` form is kept verbatim.
    html_text = '<pre><code class="language-html">a<br/>b</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert highlighter.calls == [("a<br/>b", "html")]
    assert rendered == (
        '<pre><code class="language-html"><hl>a<br/>b</hl></code></pre>'
    )


def test_comment_reemits_verbatim() -> None:
    # Arrange
    html_text = "<!-- a note --><p>body</p>"

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_comment_inside_code_is_highlighted_source() -> None:
    # Arrange — same nested-markup-is-source contract as tags
    html_text = '<pre><code class="language-html">a<!-- c -->b</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert highlighter.calls == [("a<!-- c -->b", "html")]


def test_processing_instruction_reemits_verbatim() -> None:
    # Arrange
    html_text = '<?xml version="1.0"?><p>body</p>'

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_declaration_reemits_verbatim() -> None:
    # Arrange — a declaration in author raw HTML must not silently vanish
    html_text = "<!DOCTYPE note><p>body</p>"

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_unknown_declaration_reemits_verbatim() -> None:
    # Arrange — CDATA is bogus markup in HTML5 but must round-trip, not drop
    html_text = "<p>a</p><![CDATA[payload]]>"

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_authored_entity_in_code_is_decoded_once() -> None:
    # Arrange — `&amp;amp;` renders as `&amp;` in a browser; the lexer must
    # receive the authored `&amp;` (one decode), not `&`.
    html_text = '<pre><code class="language-text">a &amp;amp; b</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert highlighter.calls == [("a &amp; b", "text")]


def test_charref_in_code_is_decoded_once() -> None:
    # Arrange
    html_text = '<pre><code class="language-text">a &#60; b</code></pre>'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert highlighter.calls == [("a < b", "text")]


def test_prose_entity_reference_reemits_verbatim() -> None:
    # Arrange — entity references outside code stay byte-faithful rather
    # than re-emitting the decoded character
    html_text = "<p>a &copy; b</p>"

    # Act
    rendered, _ = parse(html_text)

    # Assert
    assert rendered == html_text


def test_unclosed_code_capture_flushes_source_at_close() -> None:
    # Arrange — malformed author raw HTML: <code> never closed; the buffered
    # source must flush verbatim instead of dropping silently
    html_text = '<pre><code class="language-python">unclosed'

    # Act
    rendered, highlighter = parse(html_text)

    # Assert
    assert rendered == html_text
    assert highlighter.calls == []


def test_startendtag_without_parse_context_raises() -> None:
    # Arrange: get_starttag_text() is populated only mid-parse; a bare call
    # has no raw tag text to re-emit, same shape as the language-invariant
    # raise above.
    parser = CodeBlockHtmlParser(RecordingHighlighter())

    # Act / Assert
    with pytest.raises(ValueError, match="Missing start-tag text"):
        parser.handle_startendtag("br", [])
