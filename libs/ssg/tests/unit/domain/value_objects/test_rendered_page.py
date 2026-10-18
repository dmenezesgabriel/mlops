from datetime import date
from pathlib import Path

from ssg.domain.value_objects.rendered_page import RenderedPage


def test_rendered_page_allows_authors_and_readtime() -> None:
    from ssg.domain import (
        Article,
        Author,
        ContentCollection,
        Page,
        Site,
        SiteNavigation,
    )

    site = Site(title="S", description="", collections=())
    collection = ContentCollection(
        name="c",
        title="C",
        source_root=Path("."),
        output_slug="c",
        pages=(),
        videos={},
    )
    page = Page(slug="p", title="P", source_path=Path("p.md"))
    article = Article(title="P", body="<p>hi</p>", headings=())
    rendered = RenderedPage(
        site=site,
        collection=collection,
        page=page,
        article=article,
        navigation=SiteNavigation(home_href="index.html", sections=()),
        previous_link=None,
        next_link=None,
        authors=(Author(name="Alice", url="https://x"),),
        readtime_minutes=2,
        last_updated=date(2026, 1, 1),
    )
    assert rendered.authors == (Author(name="Alice", url="https://x"),)
    assert rendered.readtime_minutes == 2
