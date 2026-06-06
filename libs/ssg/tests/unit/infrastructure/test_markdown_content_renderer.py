from pathlib import Path

from ssg.domain.site import BuildContext, ContentCollection, Page
from ssg.infrastructure.markdown_content_renderer import MarkdownContentRenderer


def test_render_transcludes_source_and_copies_video(tmp_path: Path) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "script.py").write_text("def run() -> None:\n    pass\n", encoding="utf-8")
    markdown_path = source_root / "README.md"
    markdown_path.write_text(
        '{{ include_source("script.py") }}\n\n{{ embed_video("demo") }}',
        encoding="utf-8",
    )
    video_path = tmp_path / "videos" / "demo.mp4"
    video_path.parent.mkdir()
    video_path.write_bytes(b"mp4")
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos={"demo": video_path},
    )
    page = Page(slug="overview", title="Overview", source_path=markdown_path)
    build_path = tmp_path / "build"
    output_path = build_path / "sample-collection"

    # Act
    context = BuildContext(
        config_path=tmp_path / "site.yaml",
        output_path=build_path,
        collection_name=None,
        correlation_id="test",
    )
    rendered_content = MarkdownContentRenderer().render(collection, page, context)

    # Assert
    assert "def run()" in rendered_content
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
    markdown_path = source_root / "README.md"
    markdown_path.write_text('{{ include_source("feature_views.py") }}', encoding="utf-8")
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )

    # Act
    context = BuildContext(
        config_path=tmp_path / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=None,
        correlation_id="test",
    )
    rendered_content = MarkdownContentRenderer().render(
        collection,
        Page(slug="overview", title="Overview", source_path=markdown_path),
        context,
    )

    # Assert
    assert "&lt;p&gt;" not in rendered_content
    assert "</p>" not in rendered_content
    assert "from datetime import timedelta\n\nfrom data_sources" in rendered_content
    assert "\n    name=&quot;hourly_pickup_demand&quot;" in rendered_content


def test_render_converts_wikilinks_to_page_links(tmp_path: Path) -> None:
    # Arrange
    markdown_path = tmp_path / "README.md"
    markdown_path.write_text("See [[overview|Overview]].", encoding="utf-8")
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(Page(slug="overview", title="Overview", source_path=markdown_path),),
        videos={},
    )

    # Act
    context = BuildContext(
        config_path=tmp_path / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=None,
        correlation_id="test",
    )
    rendered_content = MarkdownContentRenderer().render(
        collection,
        Page(slug="details", title="Details", source_path=markdown_path),
        context,
    )

    # Assert
    assert '<a href="overview.html">Overview</a>' in rendered_content
