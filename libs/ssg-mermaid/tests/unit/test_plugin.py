"""Unit tests for the Mermaid plugin entry-point factory."""

from ssg.application.ports import HtmlPostProcessor
from ssg_mermaid.application.mermaid_processor import MermaidHtmlPostProcessor
from ssg_mermaid.infrastructure.plugin import (
    create_mermaid_html_post_processor,
)
from ssg_mermaid.infrastructure.subprocess_renderer import (
    SubprocessMermaidRenderer,
)


def test_create_mermaid_html_post_processor() -> None:
    # Arrange & Act
    processor = create_mermaid_html_post_processor()

    # Assert — public surface only: the entry-point contract is a
    # port-conforming processor whose renderer is rooted at this package
    # (where the vendored render.mjs lives).
    assert isinstance(processor, HtmlPostProcessor)
    assert isinstance(processor, MermaidHtmlPostProcessor)
    assert isinstance(processor.renderer, SubprocessMermaidRenderer)
    assert processor.renderer.package_dir.name == "ssg_mermaid"
