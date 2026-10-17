from datetime import UTC, datetime
from pathlib import Path

from ssg.application.ports.page_renderer import PageRenderer
from ssg.domain import (
    Article,
    ContentCollection,
    Page,
    RenderedIndex,
    RenderedNotFound,
    RenderedPage,
    Site,
)


def test_render_feed_emits_rss_with_absolute_urls(tmp_path: Path) -> None:
    from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer

    renderer = JinjaPageRenderer()
    page = Page(
        slug="first",
        title="First Post",
        source_path=tmp_path / "first.md",
        date=datetime(2026, 1, 15, tzinfo=UTC),
        authors=({"name": "Alice"},),
    )
    collection = ContentCollection(
        name="blog",
        title="Blog",
        source_root=tmp_path,
        output_slug="blog",
        pages=(page,),
        videos={},
        kind="posts",
    )
    site = Site(
        title="Learning Site",
        description="Rendered content collections.",
        collections=(collection,),
        url="https://example.com/docs",
        locale="en",
        default_locale="en",
    )
    article = Article(title="First Post", body="<p>Hi</p>", headings=())
    rendered_page = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=article,
        navigation=site.navigation_for(collection, page),
        previous_link=None,
        next_link=None,
    )
    rss = renderer.render_feed(site, collection, (rendered_page,))
    assert "<rss" in rss
    assert "https://example.com/docs/blog/first.html" in rss
    assert "2026" in rss


def test_render_feed_works_with_variant_protocol(tmp_path: Path) -> None:
    # Ensure the Protocol accept variant parameter (we pass None).
    class Dummy(PageRenderer):
        def render_page(self, rendered_page: RenderedPage) -> str:
            return ""

        def render_index(self, rendered_index: RenderedIndex) -> str:
            return ""

        def render_sitemap(
            self, site: Site, collections: tuple[ContentCollection, ...]
        ) -> str:
            return ""

        def render_robots_txt(self, site: Site) -> str:
            return ""

        def render_not_found(
            self, rendered_not_found: RenderedNotFound
        ) -> str:
            return ""

        def render_service_worker(self, manifest) -> str:
            return ""

        def render_version_redirect(self, site: Site, target: str) -> str:
            return ""

        def render_feed(
            self,
            site: Site,
            collection: ContentCollection,
            posts: tuple[RenderedPage, ...],
            variant=None,
        ) -> str:
            return "<rss/>"

        def assets(self) -> dict[str, str]:
            return {}

    assert (
        Dummy().render_feed(
            Site(title="T", description="", collections=()),
            ContentCollection(
                name="c",
                title="C",
                source_root=tmp_path,
                output_slug="c",
                pages=(),
                videos={},
            ),
            (),
        )
        == "<rss/>"
    )
