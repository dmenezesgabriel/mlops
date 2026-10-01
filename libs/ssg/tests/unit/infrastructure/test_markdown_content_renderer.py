from pathlib import Path

import pytest
from ssg.domain import BuildContext, ContentCollection, Page
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)


def _context(tmp_path: Path) -> BuildContext:
    return BuildContext(
        config_path=tmp_path / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=None,
        correlation_id="test",
    )


def _collection(source_root: Path) -> ContentCollection:
    return ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )


def test_render_transcludes_source_and_copies_video(tmp_path: Path) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "script.py").write_text(
        "def run() -> None:\n    pass\n", encoding="utf-8"
    )
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
    rendered_content = MarkdownContentRenderer().render(
        collection, page, context
    )

    # Assert
    assert "def run()" in rendered_content
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
    markdown_path = source_root / "README.md"
    markdown_path.write_text(
        '{{ include_source("feature_views.py") }}', encoding="utf-8"
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
    assert (
        "from datetime import timedelta\n\nfrom data_sources"
        in rendered_content
    )
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
        pages=(
            Page(slug="overview", title="Overview", source_path=markdown_path),
        ),
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


def test_render_gfm_table_to_html_table(tmp_path: Path) -> None:
    # Arrange
    markdown_path = tmp_path / "README.md"
    markdown_path.write_text(
        "| Algorithm | Pros | Cons | Decision |\n| :--- | :--- | :--- | :--- |\n| Ridge | Good | Bad | Chosen |",
        encoding="utf-8",
    )
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(
            Page(slug="overview", title="Overview", source_path=markdown_path),
        ),
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
    assert "<table" in rendered_content
    assert "<td" in rendered_content


@pytest.mark.parametrize(
    "literal",
    [
        "{{ 9 * 9 }}",
        "{{ not_a_helper }}",
        "{% set x = 5 %}",
    ],
)
def test_render_leaves_non_directive_template_syntax_literal(
    tmp_path: Path, literal: str
) -> None:
    # Arrange — only the `{{ helper("arg") }}` directives execute; every other
    # template-looking fragment is author text and must survive verbatim
    # (previously evaluated by Jinja: expressions silently, undefined names
    # aborting the build).
    source_root = tmp_path / "content"
    source_root.mkdir()
    page = Page(
        slug="overview",
        title="Overview",
        source_path=source_root / "index.md",
    )

    # Act
    rendered = MarkdownContentRenderer().render_markdown(
        literal, _collection(source_root), _context(tmp_path), page
    )

    # Assert
    assert literal in rendered
    assert "81" not in rendered


def test_render_does_not_execute_filtered_directive(tmp_path: Path) -> None:
    # Arrange — a call that isn't exactly `{{ helper("arg") }}` (here a piped
    # filter) is not a directive; it renders as text instead of invoking the
    # helper with a transformed argument.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")
    page = Page(
        slug="overview",
        title="Overview",
        source_path=source_root / "index.md",
    )

    # Act
    rendered = MarkdownContentRenderer().render_markdown(
        '{{ include_source("x.py" | upper) }}',
        _collection(source_root),
        _context(tmp_path),
        page,
    )

    # Assert — markdown escapes the quotes, but the helper never ran
    assert 'class="source-panel' not in rendered
    assert "upper" in rendered


def test_render_keeps_literal_transclusion_marker_text(
    tmp_path: Path,
) -> None:
    # Arrange — marker-shaped author text must survive; only generated
    # markers are substituted back with rendered fragments.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")
    page = Page(
        slug="overview",
        title="Overview",
        source_path=source_root / "index.md",
    )

    # Act
    rendered = MarkdownContentRenderer().render_markdown(
        'Literal: SSG_TRANSCLUSION_0\n\n{{ include_source("x.py") }}',
        _collection(source_root),
        _context(tmp_path),
        page,
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
def test_render_accepts_directive_whitespace_and_quote_variants(
    tmp_path: Path, directive: str
) -> None:
    # Arrange — pins the accepted directive grammar: helper name, one quoted
    # string argument, optional inner whitespace.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")
    page = Page(
        slug="overview",
        title="Overview",
        source_path=source_root / "index.md",
    )

    # Act
    rendered = MarkdownContentRenderer().render_markdown(
        directive, _collection(source_root), _context(tmp_path), page
    )

    # Assert
    assert 'class="source-panel' in rendered
    assert "x = 1" in rendered


def test_render_inlines_transclusion_within_paragraph(tmp_path: Path) -> None:
    # Arrange — a directive mid-sentence resolves to its marker inline, so the
    # bare-marker replace arm (not just the `<p>{marker}</p>` arm) is live.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "x.py").write_text("x = 1\n", encoding="utf-8")
    page = Page(
        slug="overview",
        title="Overview",
        source_path=source_root / "index.md",
    )

    # Act
    rendered = MarkdownContentRenderer().render_markdown(
        'before {{ include_source("x.py") }} after',
        _collection(source_root),
        _context(tmp_path),
        page,
    )

    # Assert
    assert 'class="source-panel' in rendered
    assert "before" in rendered
    assert "after" in rendered
