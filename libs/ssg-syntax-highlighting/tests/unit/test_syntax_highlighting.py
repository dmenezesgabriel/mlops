from ssg.domain import Site
from ssg_syntax_highlighting.application.syntax_highlighter import (
    CodeBlockSyntaxHighlightingProcessor,
)
from ssg_syntax_highlighting.infrastructure.plugin import (
    create_pygments_html_post_processor,
)

CODE_BLOCK = '<pre><code class="language-python">x = 1</code></pre>'


class PassThroughHighlighter:
    def highlight(self, source: str, language: str) -> str:
        return source


class RecordingHighlighterFactory:
    def __init__(self) -> None:
        self.created_style_names: list[str] = []

    def create(self, style_name: str) -> PassThroughHighlighter:
        self.created_style_names.append(style_name)
        return PassThroughHighlighter()


def empty_site(extensions: dict[str, dict[str, str]] | None = None) -> Site:
    return Site(
        title="Learning Site",
        description="",
        collections=(),
        extensions=extensions or {},
    )


def test_process_highlights_python_code_block() -> None:
    # Arrange
    processor = create_pygments_html_post_processor()
    rendered_html = '<pre><code class="language-python">def run() -&gt; None:\n    pass\n</code></pre>'

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert '<code class="language-python">' in processed_html
    assert "highlight-token" in processed_html
    assert "style=" in processed_html
    assert "def" in processed_html
    assert "run" in processed_html


def test_process_uses_gruvbox_dark_style_by_default() -> None:
    # Arrange
    processor = create_pygments_html_post_processor()
    rendered_html = '<pre><code class="language-python">def run():\n    pass\n</code></pre>'

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert "#FB4934" in processed_html


def test_process_uses_site_configured_style() -> None:
    # Arrange
    processor = create_pygments_html_post_processor()
    site = empty_site({"syntax_highlighting": {"style": "monokai"}})
    rendered_html = '<pre><code class="language-python">def run():\n    pass\n</code></pre>'

    # Act
    processed_html = processor.process(rendered_html, site)

    # Assert
    assert "#66D9EF" in processed_html


def test_process_uses_text_fallback_for_unknown_language() -> None:
    # Arrange
    processor = create_pygments_html_post_processor()
    rendered_html = '<pre><code class="language-unknown-dialect">raw &amp; safe</code></pre>'

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert "raw &amp; safe" in processed_html
    assert '<code class="language-unknown-dialect">' in processed_html


def test_process_leaves_unclassified_code_blocks_unchanged() -> None:
    # Arrange
    processor = create_pygments_html_post_processor()
    rendered_html = (
        "<p>Before</p><pre><code>plain &amp; safe</code></pre><p>After</p>"
    )

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert processed_html == rendered_html


def test_process_preserves_non_code_markup_verbatim() -> None:
    # Arrange — a prose-only page still re-serializes when it mentions
    # `language-`; non-code markup must round-trip byte-faithful
    processor = create_pygments_html_post_processor()
    rendered_html = "<p>Use language-python classes<br />here</p><!-- note -->"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert processed_html == rendered_html


def test_process_preserves_authored_entities_in_code() -> None:
    # Arrange — authored `&amp;amp;` displays `&amp;`; highlighted output must
    # re-escape back to the same bytes (exactly one decode into the lexer)
    processor = create_pygments_html_post_processor()
    rendered_html = (
        '<pre><code class="language-text">a &amp;amp; b</code></pre>'
    )

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert "a &amp;amp; b" in processed_html


def test_process_creates_one_highlighter_per_style() -> None:
    # Arrange — the style is build-invariant; rebuilding the formatter per
    # page was ~60% of a one-block page's render cost
    factory = RecordingHighlighterFactory()
    processor = CodeBlockSyntaxHighlightingProcessor(factory)

    # Act
    processor.process(CODE_BLOCK, empty_site())
    processor.process(CODE_BLOCK, empty_site())

    # Assert
    assert factory.created_style_names == ["gruvbox-dark"]


def test_process_creates_a_highlighter_per_configured_style() -> None:
    # Arrange
    factory = RecordingHighlighterFactory()
    processor = CodeBlockSyntaxHighlightingProcessor(factory)

    # Act
    processor.process(
        CODE_BLOCK, empty_site({"syntax_highlighting": {"style": "monokai"}})
    )
    processor.process(CODE_BLOCK, empty_site())
    processor.process(
        CODE_BLOCK, empty_site({"syntax_highlighting": {"style": "monokai"}})
    )

    # Assert
    assert factory.created_style_names == ["monokai", "gruvbox-dark"]


def test_process_skips_the_factory_without_code_blocks() -> None:
    # Arrange
    factory = RecordingHighlighterFactory()
    processor = CodeBlockSyntaxHighlightingProcessor(factory)

    # Act
    processed_html = processor.process("<p>no code</p>", empty_site())

    # Assert
    assert processed_html == "<p>no code</p>"
    assert factory.created_style_names == []
