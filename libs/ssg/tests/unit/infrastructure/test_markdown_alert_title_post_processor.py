import pytest
from ssg.domain import Site
from ssg.infrastructure.markdown_alert_title_post_processor import (
    MarkdownAlertTitlePostProcessor,
)


def _site(i18n: dict[str, str] | None = None) -> Site:
    return Site(
        title="Site",
        description="",
        collections=(),
        extensions={"i18n": i18n or {}},
    )


def _alert_html(kind: str, title: str) -> str:
    # The shape markdown-it's `alerts` option emits (rules_block/blockquote):
    # a div per kind whose first paragraph is the capitalized English title.
    return (
        f'<div class="markdown-alert markdown-alert-{kind}">\n'
        f'<p class="markdown-alert-title">{title}</p>\n'
        "<p>Body.</p>\n"
        "</div>\n"
    )


@pytest.mark.parametrize(
    ("kind", "title", "label_key"),
    [
        ("note", "Note", "label_alert_note"),
        ("tip", "Tip", "label_alert_tip"),
        ("important", "Important", "label_alert_important"),
        ("warning", "Warning", "label_alert_warning"),
        ("caution", "Caution", "label_alert_caution"),
    ],
)
def test_process_localizes_title_and_adds_icon(
    kind: str, title: str, label_key: str
) -> None:
    # Arrange
    site = _site({label_key: "Rótulo"})

    # Act
    processed = MarkdownAlertTitlePostProcessor().process(
        _alert_html(kind, title), site
    )

    # Assert
    assert 'class="markdown-alert-icon"' in processed
    assert "aria-hidden" in processed
    assert '<p class="markdown-alert-title">' in processed
    assert "Rótulo</p>" in processed
    assert f">{title}</p>" not in processed


def test_process_uses_english_defaults_without_i18n_settings() -> None:
    # Arrange — a site with no i18n extension keeps the capitalized kind as
    # the title, mirroring what markdown-it emits.
    processed = MarkdownAlertTitlePostProcessor().process(
        _alert_html("warning", "Warning"), _site()
    )

    assert 'class="markdown-alert-icon"' in processed
    assert "Warning</p>" in processed


def test_process_leaves_non_alert_html_untouched() -> None:
    # Arrange
    html = (
        "<blockquote>\n<p>[!NOTE] trailing text</p>\n</blockquote>\n<p>x</p>"
    )

    # Act
    processed = MarkdownAlertTitlePostProcessor().process(html, _site())

    # Assert — only the fixed alert-title paragraph is rewritten; a literal
    # marker mid-line and ordinary paragraphs pass through verbatim.
    assert processed == html


def test_process_escapes_label_text() -> None:
    # Arrange — labels come from site config; they are text, not markup.
    site = _site({"label_alert_note": "<b>bold</b>"})

    # Act
    processed = MarkdownAlertTitlePostProcessor().process(
        _alert_html("note", "Note"), site
    )

    # Assert
    assert "&lt;b&gt;bold&lt;/b&gt;" in processed
    assert "<b>bold</b>" not in processed


def test_process_is_idempotent() -> None:
    # Arrange — preview rebuilds reprocess unchanged output; a second pass
    # must not wrap or duplicate the title/icon.
    site = _site({"label_alert_tip": "Dica"})
    processor = MarkdownAlertTitlePostProcessor()
    once = processor.process(_alert_html("tip", "Tip"), site)

    # Act
    twice = processor.process(once, site)

    # Assert
    assert twice == once
