from ssg.domain.entities.article import Article


def test_article_has_table_of_contents() -> None:
    # Arrange & Act
    article_without = Article(title="Test", body="<p>Test</p>", headings=())

    # Assert
    assert article_without.has_table_of_contents() is False
