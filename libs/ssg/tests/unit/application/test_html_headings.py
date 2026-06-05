from ssg.application.html_headings import HtmlArticleOutlineBuilder, demote_top_level_headings


def test_demote_top_level_headings_preserves_heading_attributes() -> None:
    # Arrange
    rendered_html = '<h1 id="overview">Overview</h1><p>Body</p>'

    # Act
    demoted_html = demote_top_level_headings(rendered_html)

    # Assert
    assert demoted_html == '<h2 id="overview">Overview</h2><p>Body</p>'


def test_article_outline_builder_adds_stable_heading_anchors() -> None:
    # Arrange
    rendered_html = "<h2>Problem Framing</h2><p>Body</p><h3>Metric &amp; Target</h3>"

    # Act
    article = HtmlArticleOutlineBuilder().build("Overview", rendered_html)

    # Assert
    assert article.body == (
        '<h2 id="problem-framing">Problem Framing</h2><p>Body</p>'
        '<h3 id="metric-target">Metric &amp; Target</h3>'
    )
    assert [(heading.label, heading.href, heading.level) for heading in article.headings] == [
        ("Problem Framing", "#problem-framing", 2),
        ("Metric & Target", "#metric-target", 3),
    ]
    assert article.has_table_of_contents() is True


def test_article_outline_builder_preserves_existing_ids_and_deduplicates_slugs() -> None:
    # Arrange
    rendered_html = '<h2 id="custom">Overview</h2><h2>Overview</h2><h2>Overview</h2>'

    # Act
    article = HtmlArticleOutlineBuilder().build("Overview", rendered_html)

    # Assert
    assert '<h2 id="custom">Overview</h2>' in article.body
    assert '<h2 id="overview">Overview</h2>' in article.body
    assert '<h2 id="overview-2">Overview</h2>' in article.body
    assert [heading.href for heading in article.headings] == [
        "#custom",
        "#overview",
        "#overview-2",
    ]
