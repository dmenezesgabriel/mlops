from ssg_latex.application.latex_processor import LatexHtmlPostProcessor
from ssg_latex.infrastructure.subprocess_renderer import (
    SubprocessLatexRenderer,
)
from ssg_latex.presentation.plugin import create_latex_html_post_processor


def test_create_latex_html_post_processor() -> None:
    # Arrange & Act
    processor = create_latex_html_post_processor()

    # Assert
    assert isinstance(processor, LatexHtmlPostProcessor)
    assert isinstance(processor._renderer, SubprocessLatexRenderer)
    assert processor._renderer._package_dir.name == "ssg_latex"
