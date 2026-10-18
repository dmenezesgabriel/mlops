from pathlib import Path

import pytest
from ssg.application import StaticSiteBuilder
from ssg.infrastructure.html_article_outline_builder import (
    HtmlArticleOutlineBuilder,
)
from ssg.infrastructure.in_memory_dependency_tracker import (
    InMemoryDependencyTracker,
)
from ssg.infrastructure.in_memory_search_index import InMemorySearchIndex
from ssg.infrastructure.jinja_page_renderer import JinjaPageRenderer
from ssg.infrastructure.markdown_content_renderer import (
    MarkdownContentRenderer,
)
from ssg.infrastructure.site_config_repository import SiteConfigRepository
from ssg_i18n.application.i18n_site_variant_provider import (
    I18nSiteVariantProvider,
)
from ssg_i18n.application.translation import InMemoryTextTranslator


@pytest.mark.integration
def test_i18n_posts_emit_index_and_feed_per_locale(tmp_path: Path) -> None:
    # Arrange
    config_path = _write_posts_site(tmp_path)
    output_path = tmp_path / "site" / "build"
    builder = _builder(
        InMemoryTextTranslator(
            {
                "Blog": "Blogue",
                "Intro Post": "Postagem de Introducao",
                "min read": "min de leitura",
            }
        )
    )

    # Act
    builder.build(config_path, output_path)

    # Assert
    _assert_default_locale_posts(output_path)
    _assert_translated_posts(output_path)


def _builder(
    translator: InMemoryTextTranslator,
) -> StaticSiteBuilder:
    return StaticSiteBuilder(
        site_repository=SiteConfigRepository(),
        content_renderers=(MarkdownContentRenderer(),),
        page_renderer=JinjaPageRenderer(),
        site_variant_provider=I18nSiteVariantProvider(
            translator, marker_token_factory=lambda: "0123456789abcdef"
        ),
        article_outline_builder=HtmlArticleOutlineBuilder(),
        dependency_tracker=InMemoryDependencyTracker(),
        search_index=InMemorySearchIndex(),
    )


def _assert_default_locale_posts(output_path: Path) -> None:
    feed = (output_path / "blog" / "feed.xml").read_text(encoding="utf-8")
    assert "<pubDate>" in feed
    assert "<dc:creator>Ada Lovelace</dc:creator>" in feed


def _assert_translated_posts(output_path: Path) -> None:
    # kind: posts must survive localization, or the translated locale emits
    # no collection index and no feed at all.
    index_html = (output_path / "pt-BR" / "blog" / "index.html").read_text(
        encoding="utf-8"
    )
    post_list = _post_list_html(index_html)
    assert "Postagem de Introducao" in post_list
    assert "min de leitura" in post_list
    assert "Draft Post" not in post_list  # draft flag survives localization
    feed = (output_path / "pt-BR" / "blog" / "feed.xml").read_text(
        encoding="utf-8"
    )
    assert "<pubDate>" in feed  # date survives localization
    assert "<dc:creator>Ada Lovelace</dc:creator>" in feed
    assert "Draft Post" not in feed


def _post_list_html(index_html: str) -> str:
    # The sidebar navigation lists every page by title, drafts included; the
    # published set is only what sits inside the post list itself.
    start = index_html.index('class="post-list"')
    end = index_html.index("</ul>", start)
    return index_html[start:end]


def _write_posts_site(tmp_path: Path) -> Path:
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
        "    default_locale: en\n"
        "    locales: en,pt-BR\n"
        "collections:\n"
        "  - name: blog\n"
        "    title: Blog\n"
        "    kind: posts\n"
        "    source_root: ../content/blog\n"
        "    output_slug: blog\n"
        "    pages:\n"
        "      - slug: intro\n"
        "        title: Intro Post\n"
        "        source: intro.md\n"
        "        date: 2026-03-03\n"
        "        authors:\n"
        "          - Ada Lovelace\n"
        "      - slug: draft\n"
        "        title: Draft Post\n"
        "        source: draft.md\n"
        "        date: 2026-02-01\n"
        "        draft: true\n",
        encoding="utf-8",
    )
    for slug in ("intro", "draft"):
        (content_root / f"{slug}.md").write_text(
            f"# {slug.title()} Post\n\nA paragraph of prose for {slug}.\n",
            encoding="utf-8",
        )
    return site_path / "site.yaml"
