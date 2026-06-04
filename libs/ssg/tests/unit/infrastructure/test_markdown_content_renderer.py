from pathlib import Path

from ssg.domain.site import ContentCollection, Page
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
    output_path = tmp_path / "build" / "sample-collection"

    # Act
    rendered_content = MarkdownContentRenderer().render(collection, page, output_path)

    # Assert
    assert "def run()" in rendered_content
    assert '<video controls src="assets/videos/demo.mp4"></video>' in rendered_content
    assert 'class="source-panel story-step"' in rendered_content
    assert 'class="media-frame video-frame story-step"' in rendered_content
    assert (output_path / "assets" / "videos" / "demo.mp4").exists()


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
    rendered_content = MarkdownContentRenderer().render(
        collection,
        Page(slug="details", title="Details", source_path=markdown_path),
        tmp_path / "build",
    )

    # Assert
    assert '<a href="overview.html">Overview</a>' in rendered_content
