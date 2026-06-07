from ssg.domain.site import Site
from ssg_latex.application.latex_processor import (
    LatexHtmlPostProcessor,
    LatexRenderer,
)


class FakeLatexRenderer(LatexRenderer):
    def __init__(self) -> None:
        self.call_count = 0

    def render(self, expression: str, display_mode: bool) -> str:
        self.call_count += 1
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
