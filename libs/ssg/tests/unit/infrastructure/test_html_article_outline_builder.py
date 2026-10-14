import pytest
from ssg.domain import Article, demote_top_level_headings
from ssg.infrastructure.html_article_outline_builder import (
    HtmlArticleOutlineBuilder,
)

PERMALINK_LABEL = "Permalink to this section"


def build_article(title: str, rendered_html: str) -> Article:
    return HtmlArticleOutlineBuilder().build(
        title, rendered_html, PERMALINK_LABEL
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


@pytest.mark.parametrize(
    "rendered_html",
    [
        "<h2 id='keep'>Title</h2>",
        "<h2 id=keep>Title</h2>",
        '<h2 ID="keep">Title</h2>',
        '<h2 id = "keep">Title</h2>',
    ],
)
def test_article_outline_builder_keeps_existing_heading_id(
    rendered_html: str,
) -> None:
    # Act
    article = build_article("T", rendered_html)

    # Assert — the headerlink anchor is appended inside the heading; the
    # author-supplied id is preserved verbatim (never re-slugged).
    assert article.body == rendered_html.replace(
        "</h2>",
        '<a class="headerlink" href="#keep" '
        f'aria-label="{PERMALINK_LABEL}">¶</a></h2>',
    )
    assert article.headings[0].href == "#keep"


def test_article_outline_builder_ignores_id_inside_other_attribute_value() -> (
    None
):
    # Arrange
    rendered_html = '<h2 data-x="a id=5">T</h2>'

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert article.body == (
        '<h2 id="t" data-x="a id=5">T'
        f'<a class="headerlink" href="#t" '
        f'aria-label="{PERMALINK_LABEL}">¶</a></h2>'
    )
    assert article.headings[0].href == "#t"


def test_article_outline_builder_adds_stable_heading_anchors() -> None:
    # Arrange
    rendered_html = (
        "<h2>Problem Framing</h2><p>Body</p><h3>Metric &amp; Target</h3>"
    )

    # Act
    article = build_article("Overview", rendered_html)

    # Assert
    assert article.headings[0].label == "Problem Framing"
    assert article.headings[0].href == "#problem-framing"
    assert article.headings[0].level == 2
    assert article.headings[1].label == "Metric & Target"
    assert article.headings[1].href == "#metric-target"
    assert article.headings[1].level == 3


def test_article_outline_builder_dedupes_duplicate_heading_labels() -> None:
    # Arrange — repeated labels need distinct anchors: the first keeps the
    # bare slug, later occurrences get a `-N` suffix.
    rendered_html = "<h2>Overview</h2><p>Body</p><h2>Overview</h2>"

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert 'id="overview"' in article.body
    assert 'id="overview-2"' in article.body
    assert [heading.href for heading in article.headings] == [
        "#overview",
        "#overview-2",
    ]


def test_article_outline_builder_skips_heading_without_label() -> None:
    # Arrange — a heading whose body has no text gets no generated id and no
    # TOC entry; the markup passes through untouched.
    rendered_html = "<h2>   </h2><p>Body</p>"

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert article.body == rendered_html
    assert article.headings == ()


def test_article_outline_builder_falls_back_to_section_slug() -> None:
    # Arrange — a label with no slug characters ("!!!") slugifies to empty;
    # the fallback id is "section".
    rendered_html = "<h2>!!!</h2>"

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert article.body == (
        '<h2 id="section">!!!'
        f'<a class="headerlink" href="#section" '
        f'aria-label="{PERMALINK_LABEL}">¶</a></h2>'
    )
    assert article.headings[0].href == "#section"


def test_article_outline_builder_injects_headerlink_anchor() -> None:
    # Arrange — mkdocs/Python-Markdown convention: the permalink anchor sits
    # inside the heading so :hover/:target on the heading reveals it.
    rendered_html = (
        "<h2>Problem Framing</h2><p>Body</p><h3>Metric &amp; Target</h3>"
    )

    # Act
    article = build_article("Overview", rendered_html)

    # Assert — every heading self-links and the anchor href is identical to
    # the TOC entry href, so TOC and inline anchors can never diverge.
    assert article.body == (
        '<h2 id="problem-framing">Problem Framing'
        f'<a class="headerlink" href="#problem-framing" '
        f'aria-label="{PERMALINK_LABEL}">¶</a></h2>'
        "<p>Body</p>"
        '<h3 id="metric-target">Metric &amp; Target'
        f'<a class="headerlink" href="#metric-target" '
        f'aria-label="{PERMALINK_LABEL}">¶</a></h3>'
    )
    assert [heading.href for heading in article.headings] == [
        "#problem-framing",
        "#metric-target",
    ]


def test_article_outline_builder_escapes_permalink_label() -> None:
    # Arrange — the label is an attribute value; quotes must be escaped.
    rendered_html = "<h2>Title</h2>"

    # Act
    article = HtmlArticleOutlineBuilder().build(
        "T", rendered_html, 'Link "here" & <now>'
    )

    # Assert
    assert article.body == (
        '<h2 id="title">Title'
        '<a class="headerlink" href="#title" '
        'aria-label="Link &quot;here&quot; &amp; &lt;now&gt;">¶</a></h2>'
    )


def test_build_captures_section_text_between_headings() -> None:
    # Arrange — a section is a heading plus the content that follows it, up
    # to the next heading (mkdocs ContentSection).
    rendered_html = (
        "<h2>Setup</h2><p>Install it.</p><h2>Usage</h2><p>Run it.</p>"
    )

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert [heading.section_text for heading in article.headings] == [
        "Install it.",
        "Run it.",
    ]


def test_build_section_text_strips_markup_and_collapses_whitespace() -> None:
    # Arrange — mkdocs `_add_entry` normalization: tags out, runs of
    # whitespace collapse to a single space.
    rendered_html = (
        "<h2>Setup</h2><p>Install <strong>all</strong>\n   of it.</p>"
    )

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert article.headings[0].section_text == "Install all of it."


def test_build_attributes_text_after_unlabeled_heading_to_previous_section() -> (
    None
):
    # Arrange — an unlabeled heading starts no indexable section; the text
    # that follows it still belongs to the previous indexed section.
    rendered_html = "<h2>Setup</h2><p>One.</p><h2>   </h2><p>Two.</p>"

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert len(article.headings) == 1
    assert article.headings[0].section_text == "One. Two."


def test_build_plain_text_strips_tags_and_includes_preamble() -> None:
    # Arrange — the page-level entry indexes the whole body text, preamble
    # and heading labels included (mkdocs `stripped_html`).
    rendered_html = "<p>Intro text.</p><h2>Setup</h2><p>Install it.</p>"

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert article.plain_text == "Intro text. Setup Install it."


def test_build_plain_text_omits_script_and_style_blocks() -> None:
    # Arrange — notebook widget outputs can carry script/style payloads;
    # their source is not searchable text.
    rendered_html = (
        "<p>Text.</p><script>var x = 1;</script><style>.a {}</style>"
    )

    # Act
    article = build_article("T", rendered_html)

    # Assert
    assert article.plain_text == "Text."
    assert article.headings == ()
