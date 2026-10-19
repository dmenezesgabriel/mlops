from pathlib import Path

import pytest
from ssg.application import StaticSiteBuilder
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg_social.infrastructure.plugin import create_social_card_renderer


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
        content_renderers=(MarkdownContentRenderer(),),
        page_renderer=JinjaPageRenderer(),
        site_variant_provider=SingleSiteVariantProvider(),
        article_outline_builder=HtmlArticleOutlineBuilder(),
        dependency_tracker=InMemoryDependencyTracker(),
        search_index=InMemorySearchIndex(),
        social_card_renderer=create_social_card_renderer(),
    ).build(config_path, output_path)


@pytest.mark.integration
def test_posts_collection_renders_index_feed_and_read_time(
    tmp_path: Path,
) -> None:
    # Arrange
    config_path = _write_posts_site(tmp_path)
    output_path = tmp_path / "site" / "build"

    # Act
    _build_site(config_path, output_path)

    # Assert
    _assert_posts_index(output_path)
    _assert_feed(output_path)
    _assert_post_page_meta(output_path)


@pytest.mark.integration
def test_unpublished_posts_reach_no_built_artifact(tmp_path: Path) -> None:
    # Regression: the index and feed filtered drafts, but the page file, the
    # social card, the sitemap and the search index did not.
    config_path = _write_posts_site(tmp_path)
    output_path = tmp_path / "site" / "build"

    _build_site(config_path, output_path)

    for slug in ("draft", "future"):
        assert not (output_path / "blog" / f"{slug}.html").exists()
        assert not (
            output_path / "assets" / "social" / "blog" / f"{slug}.png"
        ).exists()
        assert f"blog/{slug}.html" not in _read_text(
            output_path / "sitemap.xml"
        )
        assert f"blog/{slug}.html" not in _read_text(
            output_path / "search-index.json"
        )
        # Sidebar navigation lists a collection's pages by link.
        index_html = _read_text(output_path / "blog" / "index.html")
        assert f"{slug}.html" not in index_html


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.integration
def test_all_draft_posts_collection_still_builds_an_empty_index(
    tmp_path: Path,
) -> None:
    # A blog with nothing published yet keeps its index URL instead of
    # crashing on an empty page list.
    config_path = _write_site(tmp_path, _ONLY_DRAFT_PAGES, ("draft",))
    output_path = tmp_path / "site" / "build"

    _build_site(config_path, output_path)

    assert not (output_path / "blog" / "draft.html").exists()
    index_html = _read_text(output_path / "blog" / "index.html")
    assert "Draft Post" not in index_html
    assert "<item>" not in _read_text(output_path / "blog" / "feed.xml")


def _posts_index_html(output_path: Path) -> str:
    return _read_text(output_path / "blog" / "index.html")


def _post_list_html(index_html: str) -> str:
    # The published set is what sits inside the post list; the surrounding
    # navigation carries the same published pages.
    start = index_html.index('class="post-list"')
    end = index_html.index("</ul>", start)
    return index_html[start:end]


def _assert_posts_index(output_path: Path) -> None:
    index_html = _posts_index_html(output_path)
    post_list = _post_list_html(index_html)
    _assert_published_posts(post_list)
    _assert_relative_post_links(post_list)
    _assert_index_chrome(index_html)
    # Read-time is localized through the i18n extension setting.
    assert "minutes of reading" in post_list


def _assert_published_posts(post_list: str) -> None:
    assert post_list.count('class="post-list__item"') == 2
    # Pinned post leads regardless of date; the rest sort newest first.
    assert post_list.index("Pinned Post") < post_list.index("Intro Post")
    assert "Draft Post" not in post_list
    assert "Future Post" not in post_list


def _assert_relative_post_links(post_list: str) -> None:
    # Links are relative to the collection index, not double-prefixed.
    assert 'href="intro.html"' in post_list
    assert 'href="blog/intro.html"' not in post_list


def _assert_index_chrome(index_html: str) -> None:
    # The index keeps the site chrome a reader expects and advertises its
    # feed for autodiscovery.
    assert '<header class="site-header">' in index_html
    assert '<footer class="site-footer">' in index_html
    assert 'type="application/rss+xml"' in index_html
    assert 'href="feed.xml"' in index_html


def _assert_feed(output_path: Path) -> None:
    feed = (output_path / "blog" / "feed.xml").read_text(encoding="utf-8")
    assert feed.count("<item>") == 2
    assert "<title>Intro Post</title>" in feed
    assert "<title>Pinned Post</title>" in feed
    assert "https://example.com/learning/blog/intro.html" in feed
    assert "03 Mar 2026 00:00:00 GMT" in feed
    assert "<dc:creator>Ada Lovelace</dc:creator>" in feed
    assert "Draft Post" not in feed
    assert "Future Post" not in feed


def _assert_post_page_meta(output_path: Path) -> None:
    post_html = (output_path / "blog" / "intro.html").read_text(
        encoding="utf-8"
    )
    assert 'class="page-authors"' in post_html
    assert "Ada Lovelace" in post_html
    assert "https://example.com/grace" in post_html
    assert 'class="page-readtime"' in post_html
    # The label is an i18n extension setting, not a hardcoded string.
    assert "minutes of reading" in post_html


_POSTS_PAGES = (
    "      - slug: intro\n"
    "        title: Intro Post\n"
    "        source: intro.md\n"
    "        date: 2026-03-03\n"
    "        authors:\n"
    "          - Ada Lovelace\n"
    "          - name: Grace Hopper\n"
    "            url: https://example.com/grace\n"
    "      - slug: pinned\n"
    "        title: Pinned Post\n"
    "        source: pinned.md\n"
    "        date: 2026-01-01\n"
    "        pin: true\n"
    "      - slug: draft\n"
    "        title: Draft Post\n"
    "        source: draft.md\n"
    "        date: 2026-02-01\n"
    "        draft: true\n"
    "      - slug: future\n"
    "        title: Future Post\n"
    "        source: future.md\n"
    "        date: 2999-01-01\n"
)

_ONLY_DRAFT_PAGES = (
    "      - slug: draft\n"
    "        title: Draft Post\n"
    "        source: draft.md\n"
    "        date: 2026-02-01\n"
    "        draft: true\n"
)


def _write_posts_site(tmp_path: Path) -> Path:
    return _write_site(
        tmp_path, _POSTS_PAGES, ("intro", "pinned", "draft", "future")
    )


def _write_site(
    tmp_path: Path, pages_yaml: str, slugs: tuple[str, ...]
) -> Path:
    site_path = tmp_path / "site"
    content_root = tmp_path / "content" / "blog"
    site_path.mkdir()
    content_root.mkdir(parents=True)
    (site_path / "site.yaml").write_text(
        "site:\n"
        "  title: Learning Site\n"
        "  description: Field notes.\n"
        "  url: https://example.com/learning\n"
        "extensions:\n"
        "  i18n:\n"
        "    label_min_read: minutes of reading\n"
        "collections:\n"
        "  - name: blog\n"
        "    title: Blog\n"
        "    kind: posts\n"
        "    source_root: ../content/blog\n"
        "    output_slug: blog\n"
        "    pages:\n" + pages_yaml,
        encoding="utf-8",
    )
    for slug in slugs:
        (content_root / f"{slug}.md").write_text(
            f"# {slug.title()} Post\n\nA paragraph of prose for {slug}.\n",
            encoding="utf-8",
        )
    return site_path / "site.yaml"
