"""Entry-point factory for the Mermaid HTML post-processor."""

from pathlib import Path

from ssg.application.ports import HtmlPostProcessor

from ssg_mermaid.application.mermaid_processor import MermaidHtmlPostProcessor
from ssg_mermaid.infrastructure.subprocess_renderer import (
    SubprocessMermaidRenderer,
)


def create_mermaid_html_post_processor() -> HtmlPostProcessor:
    """Instantiate the MermaidHtmlPostProcessor for the entry-point group."""
    package_dir = Path(__file__).parent.parent.resolve()
    renderer = SubprocessMermaidRenderer(package_dir)
    return MermaidHtmlPostProcessor(renderer)
