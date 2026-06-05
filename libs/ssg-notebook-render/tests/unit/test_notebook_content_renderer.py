from pathlib import Path

import nbformat
from ssg.domain.site import ContentCollection, Page
from ssg_notebook_render.notebook_content_renderer import (
    NotebookContentRenderer,
)


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
    nbformat.write(
        nbformat.v4.new_notebook(
            cells=[
                nbformat.v4.new_markdown_cell(
                    '{{ include_source("script.py") }}\n{{ embed_video("demo") }}',
                ),
            ],
        ),
        notebook_path,
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos={"demo": video_path},
    )
    page = Page(slug="feature-engineering", title="Feature Engineering", source_path=notebook_path)
    output_path = tmp_path / "build" / "sample-collection"

    # Act
    rendered_content = NotebookContentRenderer().render(collection, page, output_path)

    # Assert
    assert "def create_features()" in rendered_content
    assert '<video controls src="assets/videos/demo.mp4"></video>' in rendered_content
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
    nbformat.write(
        nbformat.v4.new_notebook(
            cells=[nbformat.v4.new_markdown_cell('{{ include_source("feature_views.py") }}')],
        ),
        notebook_path,
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        collection,
        Page(slug="overview", title="Overview", source_path=notebook_path),
        tmp_path / "build",
    )

    # Assert
    assert "&lt;p&gt;" not in rendered_content
    assert "</p>" not in rendered_content
    assert "from datetime import timedelta\n\nfrom data_sources" in rendered_content
    assert "\n    name=&quot;hourly_pickup_demand&quot;" in rendered_content


def test_render_includes_code_cell_and_stream_output(tmp_path: Path) -> None:
    # Arrange
    notebook_path = tmp_path / "feature_engineering.ipynb"
    nbformat.write(
        nbformat.v4.new_notebook(
            cells=[
                nbformat.v4.new_code_cell(
                    "print('hourly demand')",
                    outputs=[
                        nbformat.v4.new_output("stream", name="stdout", text="hourly demand\n")
                    ],
                ),
            ],
        ),
        notebook_path,
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )
    page = Page(slug="feature-engineering", title="Feature Engineering", source_path=notebook_path)

    # Act
    rendered_content = NotebookContentRenderer().render(collection, page, tmp_path / "build")

    # Assert
    assert "print(&#x27;hourly demand&#x27;)" in rendered_content
    assert "hourly demand" in rendered_content
    assert 'class="notebook-cell story-step"' in rendered_content
    assert 'class="notebook-output"' in rendered_content
