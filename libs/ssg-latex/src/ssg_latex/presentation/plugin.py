from pathlib import Path

from ssg.application.ports import HtmlPostProcessor

from ssg_latex.application.latex_processor import LatexHtmlPostProcessor
from ssg_latex.infrastructure.subprocess_renderer import (
    SubprocessLatexRenderer,
)


def create_latex_html_post_processor() -> HtmlPostProcessor:
    """Entry point factory to instantiate the LatexHtmlPostProcessor."""
    package_dir = Path(__file__).parent.parent.resolve()
    renderer = SubprocessLatexRenderer(package_dir)
    return LatexHtmlPostProcessor(renderer)
