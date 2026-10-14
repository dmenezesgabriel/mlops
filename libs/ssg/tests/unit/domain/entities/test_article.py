from ssg.domain.entities.article import Article
from ssg.domain.value_objects.article_heading import ArticleHeading
from ssg.domain.value_objects.search_index_entry import SearchIndexEntry


def test_article_has_table_of_contents() -> None:
    # Arrange & Act
    article_without = Article(title="Test", body="<p>Test</p>", headings=())

    # Assert
    assert article_without.has_table_of_contents() is False


def test_search_entries_returns_page_entry_then_section_entries() -> None:
    # Arrange — mkdocs contrib/search contract: one {title,text,location}
    # entry for the page, then one per TOC heading anchored by its href.
    article = Article(
        title="Overview",
        body="<p>Intro</p>",
        headings=(
            ArticleHeading(
                label="Setup",
                href="#setup",
                level=2,
                section_text="Install it",
            ),
            ArticleHeading(
                label="Usage",
                href="#usage",
                level=3,
                section_text="Run it",
            ),
        ),
        plain_text="Intro body",
    )

    # Act
    entries = article.search_entries("sample/overview.html")

    # Assert
    assert entries == (
        SearchIndexEntry(
            title="Overview",
            text="Intro body",
            location="sample/overview.html",
        ),
        SearchIndexEntry(
            title="Setup",
            text="Install it",
            location="sample/overview.html#setup",
        ),
        SearchIndexEntry(
            title="Usage",
            text="Run it",
            location="sample/overview.html#usage",
        ),
    )
