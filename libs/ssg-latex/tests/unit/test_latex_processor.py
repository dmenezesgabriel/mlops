import pytest
from ssg.domain import Site
from ssg_latex.application.latex_processor import (
    LatexHtmlParser,
    LatexHtmlPostProcessor,
    LatexRenderer,
)


class FakeLatexRenderer(LatexRenderer):
    def __init__(self) -> None:
        self.call_count = 0
        self.calls: list[tuple[str, bool]] = []

    def render(self, expression: str, display_mode: bool) -> str:
        self.call_count += 1
        self.calls.append((expression, display_mode))
        mode = "display" if display_mode else "inline"
        return f"<math mode={mode}>{expression}</math>"


def empty_site(extensions: dict[str, dict[str, str]] | None = None) -> Site:
    return Site(
        title="Learning Site",
        description="",
        collections=(),
        extensions=extensions or {},
    )


def test_post_processor_renders_inline_math() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>Given a TLC zone ID $z$ and hour $t+1$.</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert (
        processed_html
        == '<p>Given a TLC zone ID <math mode=inline>z</math> and hour <math mode=inline>t+1</math>.</p><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.17.0/dist/katex.min.css">'
    )


def test_post_processor_renders_display_math() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>$$y = x^2$$</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert (
        processed_html
        == '<p><math mode=display>y = x^2</math></p><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.17.0/dist/katex.min.css">'
    )


def test_post_processor_ignores_math_in_code_and_pre_tags() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = (
        "<p>Math $x$ here</p>"
        "<pre><code>$not_this$</code></pre>"
        "<script>console.log('$ignored$')</script>"
        "<style>body { content: '$ignored_css$'; }</style>"
        "<textarea>$ignored_textarea$</textarea>"
    )

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert "<math mode=inline>x</math>" in processed_html
    assert "$not_this$" in processed_html
    assert "$ignored$" in processed_html
    assert "$ignored_css$" in processed_html
    assert "$ignored_textarea$" in processed_html


def test_post_processor_caches_render_calls() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>Let $x$ be equal to $x$ and $y$ be $y$.</p>"

    # Act
    processor.process(rendered_html, empty_site())

    # Assert
    # Unique math expressions: 'x' (inline), 'y' (inline).
    # So call_count should be exactly 2.
    assert renderer.call_count == 2


def test_post_processor_injects_css_before_head_tag_if_present() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = (
        "<html><head><title>Test</title></head><body>$z$</body></html>"
    )

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert (
        processed_html
        == '<html><head><title>Test</title><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.17.0/dist/katex.min.css"></head><body><math mode=inline>z</math></body></html>'
    )


def test_post_processor_does_not_inject_css_if_no_math_rendered() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<html><head><title>Test</title></head><body>No math here</body></html>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert (
        processed_html
        == "<html><head><title>Test</title></head><body>No math here</body></html>"
    )


def test_post_processor_uses_site_configured_css_url() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    site = empty_site(
        {"latex": {"katex_css_url": "https://example.com/custom.css"}}
    )
    rendered_html = (
        "<html><head><title>Test</title></head><body>$z$</body></html>"
    )

    # Act
    processed_html = processor.process(rendered_html, site)

    # Assert
    assert (
        processed_html
        == '<html><head><title>Test</title><link rel="stylesheet" href="https://example.com/custom.css"></head><body><math mode=inline>z</math></body></html>'
    )


def test_post_processor_escapes_underscores_in_text_blocks() -> None:
    # Arrange
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>$$\\text{hour_sin} = 1$$</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert "hour\\_sin" in processed_html


@pytest.mark.parametrize(
    ("entity", "decoded"),
    [("&lt;", "<"), ("&gt;", ">"), ("&amp;", "&")],
)
def test_post_processor_renders_math_spanning_entity_ref(
    entity: str, decoded: str
) -> None:
    # Arrange — markdown emits < > & as entities inside text nodes; the
    # entity event must not split the math span before MATH_PATTERN sees it.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = f"<p>When $a {entity} b$ holds</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert renderer.calls == [(f"a {decoded} b", False)]
    assert "<math mode=inline>" in processed_html
    assert "katex.min.css" in processed_html


def test_post_processor_does_not_render_charref_dollar() -> None:
    # Arrange — &#36; is a literal $ in the text; splitting the verbatim run
    # keeps it from opening math (decode-then-split would match "$y$").
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>&#36;y$</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert renderer.calls == []
    assert processed_html == "<p>&#36;y$</p>"


def test_post_processor_keeps_entities_verbatim_outside_math() -> None:
    # Arrange — only the extracted math expression is decoded; entity text
    # outside math must be re-emitted byte-for-byte.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>Fish &amp; Chips</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert renderer.calls == []
    assert processed_html == "<p>Fish &amp; Chips</p>"


def test_post_processor_keeps_entities_verbatim_in_pre_tag() -> None:
    # Arrange — the ignored-tag check applies at flush time, so entities
    # inside <pre>/<code> stay verbatim and never reach the math split.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<pre>&lt;$x$&gt;</pre>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert renderer.calls == []
    assert processed_html == "<pre>&lt;$x$&gt;</pre>"


@pytest.mark.parametrize(
    "void_tag",
    ["<br/>", "<hr/>", '<img src="x.png"/>', "<input/>"],
)
def test_post_processor_keeps_self_closing_tags_verbatim(
    void_tag: str,
) -> None:
    # Arrange — without a handle_startendtag override the base class fires
    # start+end events, appending a phantom `</tag>` that browsers reparse
    # as real markup (`<br/>` -> `<br></br>` renders as two line breaks).
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = f"<p>a{void_tag}b</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert renderer.calls == []
    assert processed_html == rendered_html


def test_post_processor_keeps_self_closing_non_void_tag_verbatim() -> None:
    # Arrange — the phantom `</div>` emitted for `<div/>` closes the div
    # early in the browser, moving trailing content outside it.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<div/>tail"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert processed_html == "<div/>tail"


def test_post_processor_keeps_self_closing_tag_verbatim_in_pre() -> None:
    # Arrange — fidelity inside <pre>: the phantom `</br>` must not appear
    # there either; the verbatim emit is independent of the tag stack.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<pre><br/></pre>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert renderer.calls == []
    assert processed_html == "<pre><br/></pre>"


def test_post_processor_preserves_cdata_section() -> None:
    # Arrange — the base class drops `<![...]]>` (e.g. CDATA) entirely when
    # unknown_decl is not overridden; this parser re-serializes full page
    # bodies, so the section must re-emit verbatim instead of losing content.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<p>a</p><![CDATA[payload]]><p>b</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert processed_html == rendered_html


def test_post_processor_emits_canonical_end_tag() -> None:
    # Pin a documented residual: Python 3.11's parse_endtag strips end-tag
    # attributes before handle_endtag runs (no public seam exposes the raw
    # text), so `</div foo>` re-emits canonically. HTML5 treats end-tag
    # attributes as void, so there is no browser-visible harm.
    renderer = FakeLatexRenderer()
    processor = LatexHtmlPostProcessor(renderer)
    rendered_html = "<div>x</div foo>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert processed_html == "<div>x</div>"


def test_parser_startendtag_requires_raw_tag_text() -> None:
    # Arrange — get_starttag_text() is None outside the parse loop; the
    # verbatim emit raises a named invariant instead of writing `None`.
    parser = LatexHtmlParser(lambda expr, display: expr)

    # Act / Assert
    with pytest.raises(ValueError, match="Missing start-tag text"):
        parser.handle_startendtag("br", [])
