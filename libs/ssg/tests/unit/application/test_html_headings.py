from ssg.application.html_headings import demote_top_level_headings


def test_demote_top_level_headings_preserves_heading_attributes() -> None:
    # Arrange
    rendered_html = '<h1 id="overview">Overview</h1><p>Body</p>'

    # Act
    demoted_html = demote_top_level_headings(rendered_html)

    # Assert
    assert demoted_html == '<h2 id="overview">Overview</h2><p>Body</p>'
