from importlib.resources import files
from pathlib import Path

import nbformat
import pytest
from ssg.domain import BuildContext, ContentCollection, Page
from ssg_notebook_render.notebook_content_renderer import (
    NotebookContentRenderer,
    NotebookMarkdownRenderer,
)
from ssg_notebook_render.notebook_fragment_renderer import (
    NotebookFragmentRenderer,
)


def _collection(
    source_root: Path, videos: dict | None = None
) -> ContentCollection:
    return ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos=videos or {},
    )


def _page(notebook_path: Path) -> Page:
    return Page(
        slug="feature-engineering",
        title="Feature Engineering",
        source_path=notebook_path,
    )


def _context(tmp_path: Path) -> BuildContext:
    return BuildContext(
        config_path=tmp_path / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=None,
        correlation_id="test",
    )


def _write_notebook(path: Path, cells: list) -> None:
    nbformat.write(nbformat.v4.new_notebook(cells=cells), path)


def test_render_transcludes_source_and_copies_video(tmp_path: Path) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "script.py").write_text(
        "def create_features() -> None:\n    pass\n", encoding="utf-8"
    )
    notebook_path = source_root / "feature_engineering.ipynb"
    video_path = tmp_path / "videos" / "demo.mp4"
    video_path.parent.mkdir()
    video_path.write_bytes(b"mp4")
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_markdown_cell(
                '{{ include_source("script.py") }}\n{{ embed_video("demo") }}',
            ),
        ],
    )
    collection = _collection(source_root, videos={"demo": video_path})
    output_path = tmp_path / "build" / "sample-collection"

    # Act
    rendered_content = NotebookContentRenderer().render(
        collection, _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "def create_features()" in rendered_content
    assert (
        '<video controls src="assets/videos/demo.mp4"></video>'
        in rendered_content
    )
    assert 'class="source-panel story-step"' in rendered_content
    assert 'class="media-frame video-frame story-step"' in rendered_content
    assert (output_path / "assets" / "videos" / "demo.mp4").exists()


def test_render_preserves_transcluded_source_blank_lines_and_indentation(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "feature_views.py").write_text(
        "from datetime import timedelta\n\n"
        "from data_sources import hourly_demand_source\n\n"
        "hourly_pickup_demand_view = FeatureView(\n"
        '    name="hourly_pickup_demand",\n'
        ")\n",
        encoding="utf-8",
    )
    notebook_path = source_root / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_markdown_cell(
                '{{ include_source("feature_views.py") }}'
            )
        ],
    )
    collection = _collection(source_root)

    # Act
    rendered_content = NotebookContentRenderer().render(
        collection,
        Page(slug="overview", title="Overview", source_path=notebook_path),
        _context(tmp_path),
    )

    # Assert
    assert "&lt;p&gt;" not in rendered_content
    assert "</p>" not in rendered_content
    assert (
        "from datetime import timedelta\n\nfrom data_sources"
        in rendered_content
    )
    assert "\n    name=&quot;hourly_pickup_demand&quot;" in rendered_content


def test_render_includes_code_cell_and_stream_output(tmp_path: Path) -> None:
    # Arrange
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "print('hourly demand')",
                outputs=[
                    nbformat.v4.new_output(
                        "stream", name="stdout", text="hourly demand\n"
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "print(&#x27;hourly demand&#x27;)" in rendered_content
    assert "hourly demand" in rendered_content
    assert 'class="notebook-cell story-step"' in rendered_content
    assert 'class="notebook-output"' in rendered_content


def test_notebook_fragment_templates_are_package_files() -> None:
    # Arrange
    package_files = files("ssg_notebook_render")

    # Act
    code_cell_template = package_files.joinpath(
        "templates", "notebook_code_cell.html"
    )
    rendered_cell = NotebookFragmentRenderer().render_code_cell(
        "print('hourly demand')", 0, ""
    )

    # Assert
    assert code_cell_template.is_file()
    assert "notebook-cell" in code_cell_template.read_text(encoding="utf-8")
    assert 'class="notebook-cell story-step"' in rendered_cell
    assert "print(&#x27;hourly demand&#x27;)" in rendered_cell


def test_render_includes_code_cell_and_html_and_widget_output(
    tmp_path: Path,
) -> None:
    # Arrange
    notebook_path = tmp_path / "feature_engineering.ipynb"

    html_output = nbformat.v4.new_output(
        "display_data",
        data={
            "text/html": "<div>DataFrame output</div>",
            "text/plain": "DataFrame summary",
        },
    )
    widget_output = nbformat.v4.new_output(
        "display_data",
        data={
            "application/vnd.jupyter.widget-view+json": {
                "version_major": 2,
                "version_minor": 0,
                "model_id": "widget-123",
            },
            "text/plain": "InteractiveWidget",
        },
    )

    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "display()", outputs=[html_output, widget_output]
            ),
        ]
    )
    notebook.metadata.widgets = {
        "application/vnd.jupyter.widget-state+json": {
            "state": {"widget-123": {"model_name": "DropdownModel"}}
        }
    }

    nbformat.write(notebook, notebook_path)

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert (
        '<script type="application/vnd.jupyter.widget-state+json">'
        in rendered_content
    )
    assert '"widget-123"' in rendered_content
    assert (
        '<div class="notebook-output-html"><div>DataFrame output</div></div>'
        in rendered_content
    )
    assert (
        '<script type="application/vnd.jupyter.widget-view+json">'
        in rendered_content
    )
    assert '"model_id": "widget-123"' in rendered_content


@pytest.mark.parametrize(
    "literal",
    [
        "{{ 9 * 9 }}",
        "{{ not_a_helper }}",
        "{% set x = 5 %}",
    ],
)
def test_render_markdown_leaves_non_directive_template_syntax_literal(
    tmp_path: Path, literal: str
) -> None:
    # Arrange — only the `{{ helper("arg") }}` directives execute; every other
    # template-looking fragment is author text and must survive verbatim
    # (previously evaluated by Jinja: expressions silently, undefined names
    # aborting the build).
    source_root = tmp_path / "content"
    source_root.mkdir()

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        literal,
        _collection(source_root),
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert
    assert literal in rendered
    assert "81" not in rendered


def test_render_markdown_does_not_execute_filtered_directive(
    tmp_path: Path,
) -> None:
    # Arrange — a call that isn't exactly `{{ helper("arg") }}` (here a piped
    # filter) is not a directive; it renders as text instead of invoking the
    # helper with a transformed argument.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        '{{ include_source("x.py" | upper) }}',
        _collection(source_root),
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert — markdown escapes the quotes, but the helper never ran
    assert 'class="source-panel' not in rendered
    assert "upper" in rendered


def test_render_markdown_keeps_literal_transclusion_marker_text(
    tmp_path: Path,
) -> None:
    # Arrange — marker-shaped author text must survive; only generated
    # markers are substituted back with rendered fragments.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        'Literal: SSG_TRANSCLUSION_0\n\n{{ include_source("x.py") }}',
        _collection(source_root),
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert
    assert "SSG_TRANSCLUSION_0" in rendered
    assert rendered.count('class="source-panel story-step"') == 1


@pytest.mark.parametrize(
    "directive",
    [
        '{{include_source("x.py")}}',
        "{{ include_source('x.py') }}",
        '{{  include_source(  "x.py"  )  }}',
    ],
)
def test_render_markdown_accepts_directive_whitespace_and_quote_variants(
    tmp_path: Path, directive: str
) -> None:
    # Arrange — pins the accepted directive grammar: helper name, one quoted
    # string argument, optional inner whitespace.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        directive,
        _collection(source_root),
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert
    assert 'class="source-panel' in rendered
    assert "x = 1" in rendered


def test_render_markdown_inlines_transclusion_within_paragraph(
    tmp_path: Path,
) -> None:
    # Arrange — a directive mid-sentence resolves to its marker inline, so the
    # bare-marker replace arm (not just the `<p>{marker}</p>` arm) is live.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        'before {{ include_source("x.py") }} after',
        _collection(source_root),
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert
    assert 'class="source-panel' in rendered
    assert "before" in rendered
    assert "after" in rendered


def test_render_includes_error_output_ename_evalue_and_traceback(
    tmp_path: Path,
) -> None:
    # Arrange — a cell whose run raised must render the error; dropping it
    # leaves the page indistinguishable from a clean run.
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "1/0",
                outputs=[
                    nbformat.v4.new_output(
                        "error",
                        ename="ZeroDivisionError",
                        evalue="division by zero",
                        traceback=[
                            "Traceback (most recent call last):",
                            "ZeroDivisionError: division by zero",
                        ],
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "ZeroDivisionError" in rendered_content
    assert "division by zero" in rendered_content
    assert "Traceback (most recent call last):" in rendered_content


def test_render_strips_ansi_escapes_from_error_traceback(
    tmp_path: Path,
) -> None:
    # Arrange — real Jupyter tracebacks carry ANSI color codes; they must not
    # reach the page as literal escape bytes.
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "1/0",
                outputs=[
                    nbformat.v4.new_output(
                        "error",
                        ename="ZeroDivisionError",
                        evalue="division by zero",
                        traceback=[
                            "\x1b[0;31mZeroDivisionError\x1b[0m: division by zero"
                        ],
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "\x1b" not in rendered_content
    assert "ZeroDivisionError" in rendered_content


def test_render_embeds_svg_output_verbatim(tmp_path: Path) -> None:
    # Arrange — a sole-MIME svg output is author-trusted markup (same boundary
    # as the verbatim text/html arm); list-form joins like the other arms.
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "draw()",
                outputs=[
                    nbformat.v4.new_output(
                        "display_data",
                        data={
                            "image/svg+xml": [
                                '<svg xmlns="http://www.w3.org/2000/svg">',
                                '<rect width="4"/></svg>',
                            ]
                        },
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert '<svg xmlns="http://www.w3.org/2000/svg">' in rendered_content
    assert '<rect width="4"/>' in rendered_content


def test_render_shows_json_output_when_no_text_fallback(
    tmp_path: Path,
) -> None:
    # Arrange — a sole application/json output must render rather than drop
    # silently.
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "payload()",
                outputs=[
                    nbformat.v4.new_output(
                        "execute_result",
                        data={"application/json": {"rows": 3}},
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "&quot;rows&quot;: 3" in rendered_content


def test_render_prefers_text_plain_over_application_json(
    tmp_path: Path,
) -> None:
    # Arrange — with a text/plain sibling present, the curated plain repr wins
    # over the machine JSON (nbconvert-style richer-MIME priority).
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "payload()",
                outputs=[
                    nbformat.v4.new_output(
                        "execute_result",
                        data={
                            "application/json": {"rows": 3},
                            "text/plain": "curated plain repr",
                        },
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "curated plain repr" in rendered_content
    assert "&quot;rows&quot;" not in rendered_content


def test_render_escapes_script_close_tag_in_widget_state(
    tmp_path: Path,
) -> None:
    # Arrange — a `</script>` inside the serialized widget state would end the
    # script element early and leak markup into the DOM; `</` must be escaped
    # to the JSON-safe `<\/` form.
    notebook_path = tmp_path / "feature_engineering.ipynb"
    notebook = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_markdown_cell("text")],
    )
    notebook.metadata.widgets = {
        "application/vnd.jupyter.widget-state+json": {
            "state": {"m1": "</script><b>INJECTED</b>"}
        }
    }
    nbformat.write(notebook, notebook_path)

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert rendered_content.count("</script>") == 1
    assert "INJECTED" in rendered_content


def test_render_escapes_script_close_tag_in_widget_view_output(
    tmp_path: Path,
) -> None:
    # Arrange — the widget-view embed is the same `json.dumps`-into-`<script>`
    # surface as the widget state and gets the same `</` escaping.
    notebook_path = tmp_path / "feature_engineering.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "display(w)",
                outputs=[
                    nbformat.v4.new_output(
                        "display_data",
                        data={
                            "application/vnd.jupyter.widget-view+json": {
                                "model_id": "</script><b>INJECTED</b>"
                            }
                        },
                    )
                ],
            ),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert rendered_content.count("</script>") == 1
    assert "INJECTED" in rendered_content


def test_render_rejects_schema_invalid_notebook_naming_path(
    tmp_path: Path,
) -> None:
    # Arrange — nbformat raises jsonschema.ValidationError (an Exception, not
    # a ValueError) on schema-invalid notebooks; it must become a named
    # ValueError so the CLI reports it instead of tracing back.
    notebook_path = tmp_path / "broken.ipynb"
    notebook_path.write_text(
        '{"nbformat": 4, "nbformat_minor": 5, "cells": "x", "metadata": {}}',
        encoding="utf-8",
    )

    # Act / Assert
    with pytest.raises(ValueError, match="broken.ipynb"):
        NotebookContentRenderer().render(
            _collection(tmp_path), _page(notebook_path), _context(tmp_path)
        )
