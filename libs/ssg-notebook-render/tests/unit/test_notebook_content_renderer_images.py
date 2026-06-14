from pathlib import Path

import nbformat
from ssg.domain import BuildContext, ContentCollection, Page
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

    def test_should_render_notebook_embedded_image_and_copy_file_with_localized_output_path(
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
            output_path=tmp_path / "build" / "pt-BR",
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
            / "pt-BR"
            / "col-slug"
            / "assets"
            / "images"
            / "diagram.png"
        ).exists()

    def test_should_render_notebook_code_cell_output_image_with_localized_output_path(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        source_root = tmp_path / "content"
        source_root.mkdir()
        notebook_path = source_root / "overview.ipynb"

        import base64

        import nbformat

        fake_png_data = base64.b64encode(b"fake_png").decode("utf-8")
        notebook_data = nbformat.v4.new_notebook(
            cells=[
                nbformat.v4.new_code_cell(
                    source="print('hello')",
                    outputs=[
                        nbformat.v4.new_output(
                            output_type="display_data",
                            data={"image/png": fake_png_data},
                        )
                    ],
                )
            ]
        )
        nbformat.write(notebook_data, notebook_path)

        collection = ContentCollection(
            name="col",
            title="Col",
            source_root=source_root,
            output_slug="col-slug",
            pages=(),
            videos={},
        )
        page = Page(
            slug="overview", title="Overview", source_path=notebook_path
        )
        context = BuildContext(
            config_path=tmp_path / "site.yaml",
            output_path=tmp_path / "build" / "pt-BR",
            collection_name=None,
            correlation_id="test",
        )

        # Act
        rendered = NotebookContentRenderer().render(collection, page, context)

        # Assert
        assert "overview-cell-0-output-0.png" in rendered
        expected_image_path = (
            tmp_path
            / "build"
            / "pt-BR"
            / "col-slug"
            / "assets"
            / "images"
            / "overview-cell-0-output-0.png"
        )
        assert expected_image_path.exists()
        assert expected_image_path.read_bytes() == b"fake_png"
