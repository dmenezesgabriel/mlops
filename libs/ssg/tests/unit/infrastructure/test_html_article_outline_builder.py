import pytest
from ssg.domain import demote_top_level_headings
from ssg.infrastructure.html_article_outline_builder import (
    HtmlArticleOutlineBuilder,
)


def test_demote_top_level_headings_preserves_heading_attributes() -> None:
    # Arrange
    rendered_html = '<h1 id="overview">Overview</h1><p>Body</p>'

    # Act
    demoted_html = demote_top_level_headings(rendered_html)

    # Assert
    assert demoted_html == '<h2 id="overview">Overview</h2><p>Body</p>'


@pytest.mark.parametrize(
    ("rendered_html", "expected"),
    [
        ("<h1>a</h1 >", "<h2>a</h2>"),
        ("<h1>a</H1>", "<h2>a</h2>"),
        ("<H1>a</H1>", "<h2>a</h2>"),
        ("<h1>a</h1 foo>", "<h2>a</h2>"),
        ("<h1foo>a</h1foo>", "<h1foo>a</h1foo>"),
        ("<h1>a</h1><h1>b</H1 >", "<h2>a</h2><h2>b</h2>"),
    ],
)
def test_demote_top_level_headings_demotes_noncanonical_tags(
    rendered_html: str, expected: str
) -> None:
    # Act
    demoted_html = demote_top_level_headings(rendered_html)

    # Assert
    assert demoted_html == expected


def test_article_outline_builder_adds_stable_heading_anchors() -> None:
    # Arrange
    rendered_html = (
        "<h2>Problem Framing</h2><p>Body</p><h3>Metric &amp; Target</h3>"
    )

    # Act
    article = HtmlArticleOutlineBuilder().build("Overview", rendered_html)

    # Assert
    assert article.headings[0].label == "Problem Framing"
    assert article.headings[0].href == "#problem-framing"
    assert article.headings[0].level == 2
    assert article.headings[1].label == "Metric & Target"
    assert article.headings[1].href == "#metric-target"
    assert article.headings[1].level == 3
