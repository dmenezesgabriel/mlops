import base64
from pathlib import Path

import nbformat
import pytest
from ssg.application.static_site_builder import StaticSiteBuilder
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.markdown_content_renderer import MarkdownContentRenderer
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg_notebook_render.notebook_content_renderer import (
    NotebookContentRenderer,
)
from ssg_syntax_highlighting.presentation.plugin import create_pygments_html_post_processor


@pytest.mark.integration
def test_static_site_generation_from_configured_content_collection(tmp_path: Path) -> None:
    config_path = _create_site_with_notebook_collection(tmp_path)
    output_path = tmp_path / "site" / "build"
    builder = StaticSiteBuilder(
        site_repository=SiteConfigRepository(),
        content_renderers=(MarkdownContentRenderer(), NotebookContentRenderer()),
        html_post_processors=(create_pygments_html_post_processor(),),
        page_renderer=JinjaPageRenderer(),
    )

    builder.build(config_path, output_path)

    page_path = output_path / "sample-collection" / "feature-engineering.html"
    rendered_html = page_path.read_text(encoding="utf-8")
    overview_html = (output_path / "sample-collection" / "overview.html").read_text(
        encoding="utf-8"
    )
    _assert_navigation_rendered(rendered_html)
    _assert_notebook_content_rendered(rendered_html)
    _assert_syntax_highlighting_rendered(rendered_html, overview_html)
    _assert_site_files_written(output_path, page_path)


def _assert_navigation_rendered(rendered_html: str) -> None:
    assert '<a href="overview.html">Overview</a>' in rendered_html
    assert '<nav aria-label="Primary">' in rendered_html
    assert 'href="../sample-collection/overview.html"' in rendered_html
    assert 'href="../second-collection/overview.html"' not in rendered_html
    assert '<aside class="article-toc" aria-label="On this page">' in rendered_html


def _assert_notebook_content_rendered(rendered_html: str) -> None:
    assert "create_hourly_features" in rendered_html
    assert '<video controls src="assets/videos/demo.mp4"></video>' in rendered_html
    assert "feature table preview" in rendered_html
    assert '<img src="assets/images/feature-engineering-cell-1-output-1.png"' in rendered_html


def _assert_syntax_highlighting_rendered(rendered_html: str, overview_html: str) -> None:
    assert "highlight-token" in overview_html
    assert '<code class="language-python">' in overview_html
    assert "highlight-token" in rendered_html
    assert '<code class="language-python">' in rendered_html


def _assert_site_files_written(output_path: Path, page_path: Path) -> None:
    assert (output_path / "index.html").exists()
    assert (output_path / "assets" / "site.css").exists()
    assert "Second Collection" in (output_path / "index.html").read_text(encoding="utf-8")
    assert (page_path.parent / "assets" / "videos" / "demo.mp4").exists()
    assert (
        page_path.parent / "assets" / "images" / "feature-engineering-cell-1-output-1.png"
    ).exists()


def _create_site_with_notebook_collection(tmp_path: Path) -> Path:
    site_path = tmp_path / "site"
    source_root = tmp_path / "content" / "sample_collection"
    second_source_root = tmp_path / "content" / "second_collection"
    site_path.mkdir()
    source_root.mkdir(parents=True)
    second_source_root.mkdir(parents=True)
    _write_config(site_path, tmp_path)
    _write_markdown(source_root)
    _write_second_markdown(second_source_root)
    _write_source_file(source_root)
    _write_rendered_video(tmp_path)
    _write_notebook(source_root)
    return site_path / "site.yaml"


def _write_config(site_path: Path, tmp_path: Path) -> None:
    (site_path / "site.yaml").write_text(
        "site:\n"
        "  title: Learning Site\n"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    output_slug: sample-collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "      - slug: feature-engineering\n"
        "        title: Feature Engineering\n"
        "        source: notebooks/feature_engineering.ipynb\n"
        "    assets:\n"
        f"      videos:\n        demo: {tmp_path / 'videos/output/demo.mp4'}\n"
        "  - name: second_collection\n"
        "    title: Second Collection\n"
        "    source_root: ../content/second_collection\n"
        "    output_slug: second-collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n",
        encoding="utf-8",
    )


def _write_markdown(source_root: Path) -> None:
    (source_root / "README.md").write_text(
        "# Overview\n\nA content collection.\n\n"
        "```python\n"
        "def prepare_features() -> None:\n"
        "    pass\n"
        "```",
        encoding="utf-8",
    )


def _write_second_markdown(source_root: Path) -> None:
    (source_root / "README.md").write_text("# Overview\n\nAnother collection.", encoding="utf-8")


def _write_source_file(source_root: Path) -> None:
    (source_root / "src").mkdir()
    (source_root / "src" / "features.py").write_text(
        "def create_hourly_features() -> list[str]:\n    return ['pickup_count_lag_1_hour']\n",
        encoding="utf-8",
    )


def _write_rendered_video(tmp_path: Path) -> None:
    video_path = tmp_path / "videos" / "output" / "demo.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"rendered mp4 bytes")


def _write_notebook(source_root: Path) -> None:
    notebook_path = source_root / "notebooks" / "feature_engineering.ipynb"
    notebook_path.parent.mkdir()
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Feature Engineering\n\n"
                "See [[overview|Overview]].\n\n"
                '{{ include_source("src/features.py") }}\n\n'
                '{{ embed_video("demo") }}',
            ),
            nbformat.v4.new_code_cell(
                "columns = ['pickup_count_lag_1_hour']\ncolumns",
                outputs=[
                    nbformat.v4.new_output("stream", name="stdout", text="feature table preview\n"),
                    nbformat.v4.new_output(
                        "display_data",
                        data={"image/png": _one_pixel_png_base64()},
                        metadata={},
                    ),
                ],
            ),
        ],
    )
    nbformat.write(notebook, notebook_path)


def _one_pixel_png_base64() -> str:
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
    )
    return base64.b64encode(png_bytes).decode("ascii")
