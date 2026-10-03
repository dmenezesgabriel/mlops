from pathlib import Path

import pytest
from markdown_it import MarkdownIt
from ssg.domain import BuildContext, ContentCollection, Page
from ssg_notebook_render import notebook_content_renderer
from ssg_notebook_render.notebook_content_renderer import (
    NotebookMarkdownRenderer,
)


def _collection(
    source_root: Path,
    videos: dict | None = None,
    images: dict | None = None,
    pages: tuple = (),
) -> ContentCollection:
    return ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=pages,
        videos=videos or {},
        images=images or {},
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


def test_render_markdown_renders_wikilink_with_default_label(
    tmp_path: Path,
) -> None:
    # Arrange — a bare [[slug]] wikilink derives its label from the slug:
    # dashes become spaces and the text is title-cased.
    source_root = tmp_path / "content"
    source_root.mkdir()
    notebook_path = source_root / "cell.ipynb"
    collection = _collection(
        source_root,
        pages=(
            Page(
                slug="target-page",
                title="Target",
                source_path=notebook_path,
            ),
        ),
    )

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        "See [[target-page]] next",
        collection,
        _context(tmp_path),
        _page(notebook_path),
    )

    # Assert
    assert '<a href="target-page.html">Target Page</a>' in rendered


def test_render_markdown_renders_wikilink_with_explicit_label(
    tmp_path: Path,
) -> None:
    # Arrange — [[slug|label]] uses the author's label, HTML-escaped so label
    # markup can't inject elements into the page.
    source_root = tmp_path / "content"
    source_root.mkdir()
    notebook_path = source_root / "cell.ipynb"
    collection = _collection(
        source_root,
        pages=(
            Page(
                slug="target-page",
                title="Target",
                source_path=notebook_path,
            ),
        ),
    )

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        "See [[target-page|<b>the target</b>]] next",
        collection,
        _context(tmp_path),
        _page(notebook_path),
    )

    # Assert
    assert (
        '<a href="target-page.html">&lt;b&gt;the target&lt;/b&gt;</a>'
        in rendered
    )


def test_render_markdown_rejects_unknown_wikilink_slug(
    tmp_path: Path,
) -> None:
    # Arrange — a wikilink to a page outside the collection resolves through
    # page_href, which names the slug in its ValueError.
    source_root = tmp_path / "content"
    source_root.mkdir()
    notebook_path = source_root / "cell.ipynb"

    # Act / Assert
    with pytest.raises(ValueError, match="ghost-page"):
        NotebookMarkdownRenderer().render_markdown(
            "See [[ghost-page]] next",
            _collection(source_root),
            _context(tmp_path),
            _page(notebook_path),
        )


def test_include_source_marks_uppercase_suffix_language(
    tmp_path: Path,
) -> None:
    # Arrange — the language class comes from the lowercased suffix, so an
    # uppercase .PY extension must still classify as python.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "FEATURE.PY").write_text("x = 1\n", encoding="utf-8")

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        '{{ include_source("FEATURE.PY") }}',
        _collection(source_root),
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert
    assert 'class="language-python"' in rendered


def test_render_markdown_title_cases_video_and_image_captions(
    tmp_path: Path,
) -> None:
    # Arrange — directive names carry underscores; the rendered figcaption
    # shows them title-cased ("demo_video" -> "Demo Video").
    source_root = tmp_path / "content"
    source_root.mkdir()
    video_path = tmp_path / "videos" / "demo_video.mp4"
    video_path.parent.mkdir()
    video_path.write_bytes(b"mp4")
    image_path = tmp_path / "images" / "arch_diagram.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"png")
    collection = _collection(
        source_root,
        videos={"demo_video": video_path},
        images={"arch_diagram": image_path},
    )

    # Act
    rendered = NotebookMarkdownRenderer().render_markdown(
        '{{ embed_video("demo_video") }}\n{{ embed_image("arch_diagram") }}',
        collection,
        _context(tmp_path),
        _page(source_root / "cell.ipynb"),
    )

    # Assert
    assert "Demo Video" in rendered
    assert "Arch Diagram" in rendered


def test_render_markdown_raises_on_missing_video_asset(
    tmp_path: Path,
) -> None:
    # Arrange — a configured video whose file is absent must fail loudly;
    # silently skipping it would publish a page missing its media.
    source_root = tmp_path / "content"
    source_root.mkdir()
    collection = _collection(
        source_root,
        videos={"ghost": tmp_path / "videos" / "ghost.mp4"},
    )

    # Act / Assert
    with pytest.raises(FileNotFoundError, match="Missing rendered site video"):
        NotebookMarkdownRenderer().render_markdown(
            '{{ embed_video("ghost") }}',
            collection,
            _context(tmp_path),
            _page(source_root / "cell.ipynb"),
        )


def test_render_markdown_raises_on_missing_image_asset(
    tmp_path: Path,
) -> None:
    # Arrange
    source_root = tmp_path / "content"
    source_root.mkdir()
    collection = _collection(
        source_root,
        images={"ghost": tmp_path / "images" / "ghost.png"},
    )

    # Act / Assert
    with pytest.raises(FileNotFoundError, match="Missing rendered site image"):
        NotebookMarkdownRenderer().render_markdown(
            '{{ embed_image("ghost") }}',
            collection,
            _context(tmp_path),
            _page(source_root / "cell.ipynb"),
        )


def test_renderer_prefers_table_plugin_over_gfm_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — when both optional plugins are importable, the dedicated
    # table plugin wins; the GFM plugin is only the fallback. The locked
    # mdit-py-plugins (0.6.1) has no `table` submodule, so this arm is only
    # reachable with a bound plugin — pinned here against the import-order
    # drift the fallback exists for.
    used_plugins: list[str] = []

    def fake_table_plugin(markdown: MarkdownIt) -> None:
        used_plugins.append("table")

    monkeypatch.setattr(
        notebook_content_renderer, "table_plugin", fake_table_plugin
    )

    # Act
    NotebookMarkdownRenderer()

    # Assert
    assert used_plugins == ["table"]
