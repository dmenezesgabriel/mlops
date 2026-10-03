from pathlib import Path

import nbformat
import pytest
from ssg.application.ports import ContentRenderer
from ssg.domain import BuildContext, ContentCollection, Page
from ssg_notebook_render.notebook_content_renderer import (
    NotebookContentRenderer,
    create_notebook_content_renderer,
)


class RecordingDependencyTracker:
    """Named fake for the DependencyTracker port: records registrations."""

    def __init__(self) -> None:
        self.registrations: list[tuple[Page, Path]] = []

    def register_dependency(self, page: Page, path: Path) -> None:
        self.registrations.append((page, path))

    def affected_pages(self, changed_paths: set[Path]) -> set[Page]:
        return {
            page for page, path in self.registrations if path in changed_paths
        }

    def clear_page_dependencies(self, page: Page) -> None:
        self.registrations = [
            registered
            for registered in self.registrations
            if registered[0] != page
        ]

    def clear(self) -> None:
        self.registrations.clear()


def _collection(
    source_root: Path,
    videos: dict | None = None,
    images: dict | None = None,
) -> ContentCollection:
    return ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=source_root,
        output_slug="sample-collection",
        pages=(),
        videos=videos or {},
        images=images or {},
    )


def _page(notebook_path: Path) -> Page:
    return Page(
        slug="feature-engineering",
        title="Feature Engineering",
        source_path=notebook_path,
    )


def _context(
    tmp_path: Path,
    dependency_tracker: RecordingDependencyTracker | None = None,
) -> BuildContext:
    return BuildContext(
        config_path=tmp_path / "site.yaml",
        output_path=tmp_path / "build",
        collection_name=None,
        correlation_id="test",
        dependency_tracker=dependency_tracker,
    )


def _write_notebook(path: Path, cells: list) -> None:
    nbformat.write(nbformat.v4.new_notebook(cells=cells), path)


@pytest.mark.parametrize(
    ("source_name", "expected"),
    [
        ("feature.ipynb", True),
        ("feature.md", False),
        ("feature.py", False),
    ],
)
def test_can_render_accepts_ipynb_suffix_only(
    source_name: str, expected: bool
) -> None:
    # Arrange / Act / Assert — the EP contract: only .ipynb pages route here.
    assert NotebookContentRenderer().can_render(Path(source_name)) is expected


def test_render_registers_page_and_transclusion_dependencies(
    tmp_path: Path,
) -> None:
    # Arrange — every asset a page's rendering consumed must reach the
    # dependency tracker, or preview rebuilds would skip stale pages.
    source_root = tmp_path / "content"
    source_root.mkdir()
    (source_root / "helper.py").write_text("x = 1\n", encoding="utf-8")
    notebook_path = source_root / "feature.ipynb"
    video_path = tmp_path / "videos" / "demo.mp4"
    video_path.parent.mkdir()
    video_path.write_bytes(b"mp4")
    image_path = tmp_path / "images" / "arch.png"
    image_path.parent.mkdir()
    image_path.write_bytes(b"png")
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_markdown_cell(
                '{{ include_source("helper.py") }}\n'
                '{{ embed_video("demo") }}\n'
                '{{ embed_image("arch") }}'
            )
        ],
    )
    dependency_tracker = RecordingDependencyTracker()
    page = _page(notebook_path)

    # Act
    NotebookContentRenderer().render(
        _collection(
            source_root,
            videos={"demo": video_path},
            images={"arch": image_path},
        ),
        page,
        _context(tmp_path, dependency_tracker),
    )

    # Assert — every consumed asset is registered, a changed asset maps back
    # to its page, and clearing drops the page's memberships.
    assert set(dependency_tracker.registrations) == {
        (page, notebook_path),
        (page, source_root.joinpath("helper.py").resolve()),
        (page, video_path.resolve()),
        (page, image_path.resolve()),
    }
    assert dependency_tracker.affected_pages({video_path.resolve()}) == {page}
    dependency_tracker.clear_page_dependencies(page)
    assert dependency_tracker.registrations == []
    dependency_tracker.register_dependency(page, notebook_path)
    dependency_tracker.clear()
    assert dependency_tracker.registrations == []


def test_render_skips_raw_cells(tmp_path: Path) -> None:
    # Arrange — raw cells carry content markdown can't interpret (nbformat
    # spec: rendered output only); they contribute nothing to the page.
    notebook_path = tmp_path / "feature.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_markdown_cell("kept text"),
            nbformat.v4.new_raw_cell("dropped raw payload"),
        ],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "kept text" in rendered_content
    assert "dropped raw payload" not in rendered_content


def test_render_drops_output_with_only_unknown_mime_type(
    tmp_path: Path,
) -> None:
    # Arrange — a data output whose only MIME type is unknown to the renderer
    # contributes nothing rather than guessing a rendering.
    notebook_path = tmp_path / "feature.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "payload()",
                outputs=[
                    nbformat.v4.new_output(
                        "display_data",
                        data={"application/x-weird": "weird-payload"},
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
    assert 'class="notebook-cell' in rendered_content
    assert "weird-payload" not in rendered_content


def test_render_joins_traceback_lines_in_error_output(
    tmp_path: Path,
) -> None:
    # Arrange — nbformat keeps `traceback` as a list of lines (unlike
    # stream `text`, which it normalizes to str); the fragments must join
    # contiguously, not repr the list.
    notebook_path = tmp_path / "feature.ipynb"
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
                        traceback=["first line\n", "second line"],
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
    assert "first line\nsecond line" in rendered_content


def test_render_escapes_markup_in_stream_output(tmp_path: Path) -> None:
    # Arrange — stream output text is data, not markup; it must be
    # HTML-escaped or a cell printing `<em>` would inject real elements.
    notebook_path = tmp_path / "feature.ipynb"
    _write_notebook(
        notebook_path,
        [
            nbformat.v4.new_code_cell(
                "print(tag)",
                outputs=[
                    nbformat.v4.new_output(
                        "stream", name="stdout", text="<em>hi</em>"
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
    assert "&lt;em&gt;hi&lt;/em&gt;" in rendered_content
    assert "<em>hi</em>" not in rendered_content


def test_render_omits_widget_state_script_when_notebook_has_none(
    tmp_path: Path,
) -> None:
    # Arrange — the widget-state script must only appear when the notebook
    # actually carries widget metadata; a `null` script is dead markup.
    notebook_path = tmp_path / "feature.ipynb"
    _write_notebook(
        notebook_path,
        [nbformat.v4.new_markdown_cell("plain text")],
    )

    # Act
    rendered_content = NotebookContentRenderer().render(
        _collection(tmp_path), _page(notebook_path), _context(tmp_path)
    )

    # Assert
    assert "vnd.jupyter.widget-state" not in rendered_content


def test_entry_point_factory_returns_content_renderer() -> None:
    # Arrange / Act — the `ssg.renderers` entry point resolves to this
    # factory; ssg's plugin loader isinstance-checks the product against the
    # runtime_checkable ContentRenderer port.
    renderer = create_notebook_content_renderer()

    # Assert
    assert isinstance(renderer, ContentRenderer)
    assert renderer.can_render(Path("feature.ipynb")) is True
