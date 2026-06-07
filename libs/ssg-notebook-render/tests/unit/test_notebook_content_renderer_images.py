from pathlib import Path

import nbformat
from ssg.domain.site import BuildContext, ContentCollection, Page
from ssg_notebook_render.notebook_content_renderer import (
    NotebookContentRenderer,
)


class TestNotebookContentRendererImages:
    def _setup_notebook(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        source_root = tmp_path / "content"
        source_root.mkdir()
        notebook_path = source_root / "overview.ipynb"
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[
                    nbformat.v4.new_markdown_cell(
                        '{{ embed_image("diagram") }}'
                    ),
                ],
            ),
            notebook_path,
        )
        image_path = tmp_path / "diagram.png"
        image_path.write_bytes(b"png_content")
        return source_root, notebook_path, image_path

    def test_should_render_notebook_embedded_image_and_copy_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        source_root, notebook_path, image_path = self._setup_notebook(tmp_path)
        collection = ContentCollection(
            name="col",
            title="Col",
            source_root=source_root,
            output_slug="col-slug",
            pages=(),
            videos={},
            images={"diagram": image_path},
        )
        page = Page(
            slug="overview", title="Overview", source_path=notebook_path
        )
        context = BuildContext(
            config_path=tmp_path / "site.yaml",
            output_path=tmp_path / "build",
            collection_name=None,
            correlation_id="test",
        )

        # Act
        rendered = NotebookContentRenderer().render(collection, page, context)

        # Assert
        assert '<img src="assets/images/diagram.png"' in rendered
        assert (
            tmp_path
            / "build"
            / "col-slug"
            / "assets"
            / "images"
            / "diagram.png"
        ).exists()
