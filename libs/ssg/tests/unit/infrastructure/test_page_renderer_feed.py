from datetime import UTC, datetime
from pathlib import Path

from ssg.domain import (
    Article,
    Author,
    ContentCollection,
    Page,
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
        authors=(Author(name="Alice"),),
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
