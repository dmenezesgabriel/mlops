from pathlib import Path

from ssg.domain.site import ContentCollection
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer


def test_render_page_includes_collection_title_page_title_and_body(tmp_path: Path) -> None:
    # Arrange
    renderer = JinjaPageRenderer()
    collection = ContentCollection(
        name="sample_collection",
        title="Sample Collection",
        source_root=tmp_path,
        output_slug="sample-collection",
        pages=(),
        videos={},
    )

    # Act
    rendered_page = renderer.render_page(
        collection=collection,
        page_slug="overview",
        title="Overview",
        body="<p>Rendered content.</p>",
    )

    # Assert
    assert "Overview - Sample Collection" in rendered_page
    assert '<article data-page-slug="overview">' in rendered_page
    assert "<p>Rendered content.</p>" in rendered_page
