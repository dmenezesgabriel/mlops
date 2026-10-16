import base64
import json
from pathlib import Path

import nbformat
import pytest
from PIL import Image
from ssg.application import StaticSiteBuilder
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.markdown_alert_title_post_processor import (
    MarkdownAlertTitlePostProcessor,
)
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg_notebook_render.notebook_content_renderer import (
    NotebookContentRenderer,
)
from ssg_social.infrastructure.plugin import create_social_card_renderer
from ssg_syntax_highlighting.infrastructure.plugin import (
    create_pygments_html_post_processor,
)


def _build_site(config_path: Path, output_path: Path) -> None:
    from ssg.infrastructure.html_article_outline_builder import (
        HtmlArticleOutlineBuilder,
    )
    from ssg.infrastructure.in_memory_dependency_tracker import (
        InMemoryDependencyTracker,
    )
    from ssg.infrastructure.in_memory_search_index import InMemorySearchIndex
    from ssg.infrastructure.single_site_variant_provider import (
        SingleSiteVariantProvider,
    )

    StaticSiteBuilder(
        site_repository=SiteConfigRepository(),
        content_renderers=(
            MarkdownContentRenderer(),
            NotebookContentRenderer(),
        ),
        html_post_processors=(
            MarkdownAlertTitlePostProcessor(),
            create_pygments_html_post_processor(),
        ),
        page_renderer=JinjaPageRenderer(),
        site_variant_provider=SingleSiteVariantProvider(),
        article_outline_builder=HtmlArticleOutlineBuilder(),
        dependency_tracker=InMemoryDependencyTracker(),
        search_index=InMemorySearchIndex(),
        social_card_renderer=create_social_card_renderer(),
    ).build(config_path, output_path)


@pytest.mark.integration
def test_static_site_generation_from_configured_content_collection(
    tmp_path: Path,
) -> None:
    config_path = _create_site_with_notebook_collection(tmp_path)
    output_path = tmp_path / "site" / "build"
    _build_site(config_path, output_path)

    page_path = output_path / "sample-collection" / "feature-engineering.html"
    rendered_html = page_path.read_text(encoding="utf-8")
    overview_html = (
        output_path / "sample-collection" / "overview.html"
    ).read_text(encoding="utf-8")
    _assert_navigation_rendered(rendered_html)
    _assert_head_metadata(rendered_html, output_path)
    _assert_social_metadata(rendered_html)
    _assert_notebook_content_rendered(rendered_html)
    _assert_syntax_highlighting_rendered(rendered_html, overview_html)
    _assert_alert_rendered(overview_html)
    _assert_site_files_written(output_path, page_path)
    _assert_seo_files_written(output_path)
    _assert_social_cards_written(output_path)
    _assert_not_found_written(output_path)
    _assert_service_worker_written(output_path)


def _assert_head_metadata(rendered_html: str, output_path: Path) -> None:
    assert (
        '<link rel="canonical" '
        'href="https://example.com/learning/'
        'sample-collection/feature-engineering.html">' in rendered_html
    )
    assert '<meta property="og:type" content="article">' in rendered_html
    assert (
        '<meta property="og:url" '
        'content="https://example.com/learning/'
        'sample-collection/feature-engineering.html">' in rendered_html
    )
    assert (
        '<link rel="icon" href="../assets/favicon.svg" '
        'type="image/svg+xml">' in rendered_html
    )
    assert (
        '<meta name="ssg:service-worker" content="../sw.js">' in rendered_html
    )
    index_html = (output_path / "index.html").read_text(encoding="utf-8")
    assert (
        '<link rel="canonical" href="https://example.com/learning/">'
        in index_html
    )
    assert '<meta property="og:type" content="website">' in index_html


def _assert_social_metadata(rendered_html: str) -> None:
    # The generated per-page card wins over the configured static
    # site.image; both stay absolute under site.url.
    card_url = (
        "https://example.com/learning/assets/social/"
        "sample-collection/feature-engineering.png"
    )
    assert f'<meta property="og:image" content="{card_url}">' in rendered_html
    assert (
        '<meta property="og:image:type" content="image/png">' in rendered_html
    )
    assert '<meta property="og:image:width" content="1200">' in rendered_html
    assert '<meta property="og:image:height" content="630">' in rendered_html
    assert (
        '<meta name="twitter:card" content="summary_large_image">'
        in rendered_html
    )
    assert (
        '<meta name="twitter:title" '
        'content="Feature Engineering - Sample Collection">' in rendered_html
    )
    assert f'<meta name="twitter:image" content="{card_url}">' in rendered_html
    # Single-variant build: no other locale exists to alternate to.
    assert 'rel="alternate"' not in rendered_html


def _assert_navigation_rendered(rendered_html: str) -> None:
    assert '<a href="overview.html">Overview</a>' in rendered_html
    assert '<nav aria-label="Primary">' in rendered_html
    assert 'href="../sample-collection/overview.html"' in rendered_html
    assert 'href="../second-collection/overview.html"' not in rendered_html
    assert (
        '<aside class="article-toc" aria-label="On this page">'
        in rendered_html
    )


def _assert_notebook_content_rendered(rendered_html: str) -> None:
    assert "create_hourly_features" in rendered_html
    assert (
        '<video controls src="assets/videos/demo.mp4"></video>'
        in rendered_html
    )
    assert "feature table preview" in rendered_html
    assert (
        '<img src="assets/images/feature-engineering-cell-1-output-1.png"'
        in rendered_html
    )


def _assert_syntax_highlighting_rendered(
    rendered_html: str, overview_html: str
) -> None:
    assert "highlight-token" in overview_html
    assert '<code class="language-python">' in overview_html
    assert "highlight-token" in rendered_html
    assert '<code class="language-python">' in rendered_html


def _assert_alert_rendered(overview_html: str) -> None:
    assert '<div class="markdown-alert markdown-alert-note">' in overview_html
    assert 'class="markdown-alert-title"' in overview_html
    assert 'class="markdown-alert-icon"' in overview_html
    assert "Reproducible builds matter." in overview_html


def _assert_site_files_written(output_path: Path, page_path: Path) -> None:
    assert (output_path / "index.html").exists()
    assert (output_path / "assets" / "site.css").exists()
    assert (output_path / "assets" / "favicon.svg").exists()
    search_index = json.loads(
        (output_path / "search-index.json").read_text(encoding="utf-8")
    )
    index_locations = [entry["location"] for entry in search_index["docs"]]
    assert "sample-collection/overview.html" in index_locations
    assert (
        "sample-collection/feature-engineering.html#feature-engineering"
        in index_locations
    )
    assert "Second Collection" in (output_path / "index.html").read_text(
        encoding="utf-8"
    )
    assert (page_path.parent / "assets" / "videos" / "demo.mp4").exists()
    assert (
        page_path.parent
        / "assets"
        / "images"
        / "feature-engineering-cell-1-output-1.png"
    ).exists()


def _assert_seo_files_written(output_path: Path) -> None:
    sitemap_xml = (output_path / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.com/learning/</loc>" in sitemap_xml
    assert (
        "<loc>https://example.com/learning/"
        "sample-collection/feature-engineering.html</loc>"
    ) in sitemap_xml
    assert (
        "<loc>https://example.com/learning/second-collection/overview.html</loc>"
        in sitemap_xml
    )
    robots_txt = (output_path / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *" in robots_txt
    assert "Sitemap: https://example.com/learning/sitemap.xml" in robots_txt
    # The configured site.image ships per variant for og:image/twitter:image.
    assert (output_path / "assets" / "card.png").read_bytes() == (
        _one_pixel_png()
    )


def _assert_social_cards_written(output_path: Path) -> None:
    social_dir = output_path / "assets" / "social"
    for relative in (
        "index.png",
        "sample-collection/overview.png",
        "sample-collection/feature-engineering.png",
        "second-collection/overview.png",
    ):
        card_path = social_dir / relative
        assert card_path.exists(), f"missing generated card {relative}"
        assert Image.open(card_path).size == (1200, 630)


def _assert_service_worker_written(output_path: Path) -> None:
    service_worker = (output_path / "sw.js").read_text(encoding="utf-8")
    # The precache mirrors the emitted tree — including the scope root —
    # while video payloads stay network-only (a quota-rejected addAll would
    # abort the worker install).
    for expected in (
        '"./"',
        '"index.html"',
        '"404.html"',
        '"sitemap.xml"',
        '"search-index.json"',
        '"assets/site.css"',
        '"assets/card.png"',
        '"sample-collection/overview.html"',
        '"sample-collection/assets/images/'
        'feature-engineering-cell-1-output-1.png"',
    ):
        assert expected in service_worker
    assert "assets/videos/demo.mp4" not in service_worker
    # Social cards are crawler-only payloads; precaching them would inflate
    # every visitor's install.
    assert "assets/social/" not in service_worker
    assert 'addEventListener("fetch"' in service_worker


def _assert_not_found_written(output_path: Path) -> None:
    not_found_html = (output_path / "404.html").read_text(encoding="utf-8")
    assert '<section class="not-found' in not_found_html
    assert "Page not found" in not_found_html
    assert '<header class="site-header">' in not_found_html
    assert '<footer class="site-footer">' in not_found_html
    assert (
        'href="https://example.com/learning/assets/site.css"' in not_found_html
    )
    assert 'href="https://example.com/learning/index.html"' in not_found_html
    # No card is generated for the 404 page — it keeps the static image.
    assert (
        '<meta property="og:image" '
        'content="https://example.com/learning/assets/card.png">'
        in not_found_html
    )


_VERSIONING_CONFIG = (
    "  versioning:\n"
    '    current: "0.1"\n'
    "    default: latest\n"
    "    versions:\n"
    '      - id: "0.1"\n'
    "        aliases: [latest]\n"
    '      - id: "0.0"\n'
)


@pytest.mark.integration
def test_versioned_site_generation_emits_layout_switcher_and_registry(
    tmp_path: Path,
) -> None:
    # Arrange — same fixture as the unversioned build plus the versioning
    # block; 0.0 is declared but undeployed so it must stay out of the
    # static switcher links.
    config_path = _create_site_with_notebook_collection(
        tmp_path, site_extra=_VERSIONING_CONFIG
    )
    output_path = tmp_path / "site" / "build"

    # Act
    _build_site(config_path, output_path)

    # Assert — the mike-style layout: one real tree per version, aliases
    # as copies, a redirect + 404 + registry at the artifact root.
    _assert_versioned_layout(output_path)
    _assert_version_registry(output_path)
    version_root = output_path / "0.1"
    rendered_html = (
        version_root / "sample-collection" / "feature-engineering.html"
    ).read_text(encoding="utf-8")
    _assert_versioned_urls(rendered_html, version_root)
    _assert_version_switcher(rendered_html)


def _assert_versioned_layout(output_path: Path) -> None:
    # Content lives under the version dir, never at the artifact root; the
    # declared-but-undeployed 0.0 must not produce a tree.
    version_root = output_path / "0.1"
    assert (version_root / "index.html").exists()
    assert (
        version_root / "sample-collection" / "feature-engineering.html"
    ).exists()
    assert not (version_root / "pt-BR" / "index.html").exists()
    assert not (output_path / "sample-collection").exists()
    assert not (output_path / "0.0").exists()


def _assert_version_registry(output_path: Path) -> None:
    # `latest` is a byte-copy permalink namespace; the root carries the
    # redirect stub, the host-served 404 and the accumulated registry.
    assert (output_path / "latest" / "index.html").exists()
    assert (
        output_path / "latest" / "sample-collection" / "overview.html"
    ).exists()
    assert (output_path / "404.html").exists()
    root_index = (output_path / "index.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh" content="0; url=./0.1/"' in root_index
    versions = json.loads(
        (output_path / "versions.json").read_text(encoding="utf-8")
    )
    assert versions == [
        {"version": "0.1", "title": "0.1", "aliases": ["latest"]}
    ]


def _assert_versioned_urls(rendered_html: str, version_root: Path) -> None:
    # canonical/og:url/sitemap all carry the version segment (absolute_url
    # prefixes it), giving each version its own identity.
    assert (
        '<link rel="canonical" '
        'href="https://example.com/learning/0.1/'
        'sample-collection/feature-engineering.html">' in rendered_html
    )
    sitemap_xml = (version_root / "sitemap.xml").read_text(encoding="utf-8")
    assert "<loc>https://example.com/learning/0.1/</loc>" in sitemap_xml
    assert (
        "<loc>https://example.com/learning/0.1/"
        "sample-collection/feature-engineering.html</loc>" in sitemap_xml
    )


def _assert_version_switcher(rendered_html: str) -> None:
    assert 'class="version-switcher"' in rendered_html
    assert "data-version-switcher" in rendered_html
    # The page sits one dir under the version root: the static self link
    # and the data-version-segment hook the JS same-page resolver uses.
    assert 'data-version-segment="0.1"' in rendered_html
    assert 'data-version-segment="0.0"' not in rendered_html


def _create_site_with_notebook_collection(
    tmp_path: Path, site_extra: str = ""
) -> Path:
    site_path = tmp_path / "site"
    source_root = tmp_path / "content" / "sample_collection"
    second_source_root = tmp_path / "content" / "second_collection"
    site_path.mkdir()
    source_root.mkdir(parents=True)
    second_source_root.mkdir(parents=True)
    (site_path / "card.png").write_bytes(_one_pixel_png())
    _write_config(site_path, tmp_path, site_extra)
    _write_markdown(source_root)
    _write_second_markdown(second_source_root)
    _write_source_file(source_root)
    _write_rendered_video(tmp_path)
    _write_notebook(source_root)
    return site_path / "site.yaml"


def _write_config(
    site_path: Path, tmp_path: Path, site_extra: str = ""
) -> None:
    (site_path / "site.yaml").write_text(
        "site:\n"
        "  title: Learning Site\n"
        "  url: https://example.com/learning\n"
        "  image: card.png\n"
        f"{site_extra}"
        "collections:\n"
        "  - name: sample_collection\n"
        "    title: Sample Collection\n"
        "    source_root: ../content/sample_collection\n"
        "    output_slug: sample-collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n"
        "      - slug: feature-engineering\n"
        "        title: Feature Engineering\n"
        "        source: notebooks/feature_engineering.ipynb\n"
        "    assets:\n"
        f"      videos:\n        demo: {tmp_path / 'videos/output/demo.mp4'}\n"
        "  - name: second_collection\n"
        "    title: Second Collection\n"
        "    source_root: ../content/second_collection\n"
        "    output_slug: second-collection\n"
        "    pages:\n"
        "      - slug: overview\n"
        "        title: Overview\n"
        "        source: README.md\n",
        encoding="utf-8",
    )


def _write_markdown(source_root: Path) -> None:
    (source_root / "README.md").write_text(
        "# Overview\n\nA content collection.\n\n"
        "> [!NOTE]\n> Reproducible builds matter.\n\n"
        "```python\n"
        "def prepare_features() -> None:\n"
        "    pass\n"
        "```",
        encoding="utf-8",
    )


def _write_second_markdown(source_root: Path) -> None:
    (source_root / "README.md").write_text(
        "# Overview\n\nAnother collection.", encoding="utf-8"
    )


def _write_source_file(source_root: Path) -> None:
    (source_root / "src").mkdir()
    (source_root / "src" / "features.py").write_text(
        "def create_hourly_features() -> list[str]:\n    return ['pickup_count_lag_1_hour']\n",
        encoding="utf-8",
    )


def _write_rendered_video(tmp_path: Path) -> None:
    video_path = tmp_path / "videos" / "output" / "demo.mp4"
    video_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"rendered mp4 bytes")


def _write_notebook(source_root: Path) -> None:
    notebook_path = source_root / "notebooks" / "feature_engineering.ipynb"
    notebook_path.parent.mkdir()
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_markdown_cell(
                "# Feature Engineering\n\n"
                "See [[overview|Overview]].\n\n"
                '{{ include_source("src/features.py") }}\n\n'
                '{{ embed_video("demo") }}',
            ),
            nbformat.v4.new_code_cell(
                "columns = ['pickup_count_lag_1_hour']\ncolumns",
                outputs=[
                    nbformat.v4.new_output(
                        "stream", name="stdout", text="feature table preview\n"
                    ),
                    nbformat.v4.new_output(
                        "display_data",
                        data={"image/png": _one_pixel_png_base64()},
                        metadata={},
                    ),
                ],
            ),
        ],
    )
    nbformat.write(notebook, notebook_path)


def _one_pixel_png() -> bytes:
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
    )


def _one_pixel_png_base64() -> str:
    return base64.b64encode(_one_pixel_png()).decode("ascii")
