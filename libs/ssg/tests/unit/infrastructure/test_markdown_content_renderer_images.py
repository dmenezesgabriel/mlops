from pathlib import Path

import pytest
from ssg.domain.site import BuildContext, ContentCollection, Page
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)
from ssg.infrastructure.site_config_repository import SiteConfigRepository


class TestContentCollectionImages:
    def test_should_resolve_image_path_when_valid(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        image_file = tmp_path / "diagram.png"
        image_file.write_bytes(b"png")
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample",
            pages=(),
            videos={},
            images={"diagram": image_file},
        )

        # Act
        resolved_path = collection.image_path("diagram")

        # Assert
        assert resolved_path == image_file

    def test_should_raise_value_error_for_unknown_image(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        collection = ContentCollection(
            name="sample_collection",
            title="Sample Collection",
            source_root=tmp_path,
            output_slug="sample",
            pages=(),
            videos={},
            images={},
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            collection.image_path("diagram")
        assert "diagram" in str(exc_info.value)


class TestSiteConfigRepositoryImages:
    def test_should_parse_images_assets_mapping(self, tmp_path: Path) -> None:
        # Arrange
        site_path = tmp_path / "site"
        site_path.mkdir()
        config_path = site_path / "site.yaml"
        config_path.write_text(
            "site:\n"
            "  title: Test Site\n"
            "collections:\n"
            "  - name: test_col\n"
            "    title: Test Collection\n"
            "    source_root: .\n"
            "    pages:\n"
            "      - slug: overview\n"
            "        title: Overview\n"
            "        source: index.md\n"
            "    assets:\n"
            "      images:\n"
            "        diagram: ../diagram.png\n"
        )
        repository = SiteConfigRepository()

        # Act
        site = repository.load(config_path)

        # Assert
        collection = site.collections[0]
        assert "diagram" in collection.images
        assert collection.images["diagram"].name == "diagram.png"


class TestMarkdownContentRendererImages:
    def _setup_files(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        source_root = tmp_path / "content"
        source_root.mkdir()
        markdown_path = source_root / "index.md"
        markdown_path.write_text(
            '{{ embed_image("diagram") }}', encoding="utf-8"
        )
        image_path = tmp_path / "diagram.png"
        image_path.write_bytes(b"png_content")
        return source_root, markdown_path, image_path

    def test_should_render_embedded_image_and_copy_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        source_root, markdown_path, image_path = self._setup_files(tmp_path)
        collection = ContentCollection(
            name="col",
            title="Col",
            source_root=source_root,
            output_slug="col-slug",
            pages=(),
            videos={},
            images={"diagram": image_path},
        )
        page = Page(slug="index", title="Index", source_path=markdown_path)
        context = BuildContext(
            config_path=tmp_path / "site.yaml",
            output_path=tmp_path / "build",
            collection_name=None,
            correlation_id="test",
        )

        # Act
        rendered = MarkdownContentRenderer().render(collection, page, context)

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
