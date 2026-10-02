from ssg.application.ports import HtmlPostProcessor
from ssg_latex.application.latex_processor import LatexHtmlPostProcessor
from ssg_latex.infrastructure.plugin import create_latex_html_post_processor
from ssg_latex.infrastructure.subprocess_renderer import (
    SubprocessLatexRenderer,
)


def test_create_latex_html_post_processor() -> None:
    # Arrange & Act
    processor = create_latex_html_post_processor()

    # Assert — public surface only: the entry-point contract is a
    # port-conforming processor whose renderer is rooted at this package
    # (where the vendored katex cli.js lives).
    assert isinstance(processor, HtmlPostProcessor)
    assert isinstance(processor, LatexHtmlPostProcessor)
    assert isinstance(processor.renderer, SubprocessLatexRenderer)
    assert processor.renderer.package_dir.name == "ssg_latex"
