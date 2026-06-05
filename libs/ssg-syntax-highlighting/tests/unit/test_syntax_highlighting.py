from ssg.domain.site import Site
from ssg_syntax_highlighting.presentation.plugin import create_pygments_html_post_processor


def empty_site(extensions: dict[str, dict[str, str]] | None = None) -> Site:
    return Site(title="Learning Site", description="", collections=(), extensions=extensions or {})


def test_process_highlights_python_code_block() -> None:
    # Arrange
    processor = create_pygments_html_post_processor()
    rendered_html = (
        '<pre><code class="language-python">def run() -&gt; None:\n    pass\n</code></pre>'
    )

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
    rendered_html = "<p>Before</p><pre><code>plain &amp; safe</code></pre><p>After</p>"

    # Act
    processed_html = processor.process(rendered_html, empty_site())

    # Assert
    assert processed_html == rendered_html
