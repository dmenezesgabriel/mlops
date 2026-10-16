"""Unit tests for the pure text-fitting helpers behind the card renderer."""

import pytest
from ssg_social.application.card_text_layout import fit_font_size, wrap_lines


def _measure(text: str) -> float:
    # Fixed 10px per character — deterministic wrap math without a font.
    return float(len(text) * 10)


def test_wrap_lines_returns_single_line_when_text_fits() -> None:
    assert wrap_lines("alpha beta", _measure, max_width=200, max_lines=3) == (
        "alpha beta",
    )


def test_wrap_lines_splits_words_across_lines_at_width() -> None:
    # 10px/char: "alpha beta" = 110px fits 120; adding "gamma" overflows.
    assert wrap_lines(
        "alpha beta gamma", _measure, max_width=120, max_lines=3
    ) == ("alpha beta", "gamma")


def test_wrap_lines_ellipsizes_when_lines_exceed_max() -> None:
    lines = wrap_lines(
        "alpha beta gamma delta epsilon",
        _measure,
        max_width=120,
        max_lines=2,
    )
    assert len(lines) == 2
    assert lines[1].endswith("...")


def test_wrap_lines_replaces_last_word_with_ellipsis_when_it_overflows() -> (
    None
):
    # One allowed line at 120px: "alpha beta" is 110px and "..." (30px) does
    # not fit after it, so the last word is swapped for the ellipsis.
    lines = wrap_lines(
        "alpha beta gamma", _measure, max_width=120, max_lines=1
    )
    assert lines == ("alpha ...",)


def test_wrap_lines_rebalances_two_lines_for_even_length() -> None:
    # "one two three four" + "five" is lopsided; moving "four" evens the
    # character lengths, so the boundary word migrates to the last line.
    assert wrap_lines(
        "one two three four five", _measure, max_width=170, max_lines=3
    ) == ("one two three", "four five")


def test_wrap_lines_keeps_unbalanced_split_when_move_is_worse() -> None:
    assert wrap_lines(
        "aaaa bbbb cc dd", _measure, max_width=100, max_lines=3
    ) == ("aaaa bbbb", "cc dd")


def test_wrap_lines_empty_text_returns_no_lines() -> None:
    assert wrap_lines("   ", _measure, max_width=100, max_lines=3) == ()


def test_wrap_lines_tolerates_word_wider_than_line() -> None:
    # An unbreakable word over max_width still lands on its own line;
    # clipping at the canvas edge is the caller's concern.
    lines = wrap_lines(
        "supercalifragilisticexpialidocious ok",
        _measure,
        max_width=100,
        max_lines=3,
    )
    assert lines[0] == "supercalifragilisticexpialidocious"


def test_fit_font_size_scales_font_to_fill_box_at_max_lines() -> None:
    # metrics probe: ascender = size, descender = size/4. Box 310px over
    # 3 lines at 1.25 line-height → extent 3750 at size 1000.
    size, spacing = fit_font_size(
        lambda size: (size, size // 4),
        box_height=310,
        max_lines=3,
        line_height=1.25,
    )
    assert size == 82
    assert spacing == pytest.approx(20.6667, rel=1e-3)
