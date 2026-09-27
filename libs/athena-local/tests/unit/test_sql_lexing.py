"""Shared SQL text scanner tests (``athena_local.sql_lexing``).

``quoted_end`` and ``string_end`` share one scan core but keep distinct
unterminated-span contracts: ``string_end`` answers None so callers can
bail on malformed SQL, while ``quoted_end`` answers ``len(text)`` for
callers that swallow the tail (placeholder binding, backtick
normalization). ``strip_comments`` drops ``--``/``/* */`` noise without
touching comment markers inside ``'…'`` literals.
"""

from __future__ import annotations

import time

from athena_local import sql_lexing
from athena_local.sql_lexing import quoted_end, string_end, strip_comments


def test_quoted_end_returns_index_past_the_closing_quote() -> None:
    assert quoted_end("select 'a' x", 7, "'") == 10
    assert quoted_end('from "t" x', 5, '"') == 8
    assert quoted_end("from `t` x", 5, "`") == 8


def test_quoted_end_skips_doubled_quote_escapes() -> None:
    # 'a''b' — the inner '' is literal text, not the closing quote.
    assert quoted_end("'a''b' tail", 0, "'") == 6
    assert quoted_end('"a""b" tail', 0, '"') == 6


def test_quoted_end_unterminated_swallows_to_len() -> None:
    text = "x 'unterminated"
    assert quoted_end(text, 2, "'") == len(text)
    # A span ending exactly at len(text) is terminated — same index.
    assert quoted_end("'a'", 0, "'") == 3


def test_string_end_unterminated_returns_none() -> None:
    assert string_end("'unterminated", 0) is None
    assert string_end("'a'", 0) == 3


def test_strip_comments_drops_line_and_block_comments() -> None:
    assert strip_comments("select 1 -- tail\nfrom t") == "select 1 \nfrom t"
    assert strip_comments("a /* mid */ b") == "a  b"


def test_strip_comments_preserves_markers_inside_literals() -> None:
    assert strip_comments("'-- x' /* real */ '/* y */'") == "'-- x'  '/* y */'"


def test_strip_comments_unterminated_block_swallows_tail() -> None:
    assert strip_comments("select 1 /* never closed") == "select 1 "


def test_strip_comments_keeps_escaped_quotes_whole() -> None:
    # 'a''--' — the '' escape must not split the literal before the marker.
    assert strip_comments("'a''--x' -- c") == "'a''--x' "


def test_strip_comments_keeps_unterminated_literal_verbatim() -> None:
    # 'a'' never closes — every character stays literal text.
    assert strip_comments("'a''") == "'a''"


def test_strip_comments_backtracks_off_last_escape_pair() -> None:
    # 'a''/*' reads as one literal: the closing ' is borrowed from the last
    # '' pair, so the /* inside stays literal text, not a comment opener.
    assert strip_comments("'a''/*'") == "'a''/*'"


def test_comment_regex_matches_tokens_not_characters() -> None:
    # A per-character catch-all once made the scanner yield ~262k matches
    # at the QueryString cap; token-free text must produce zero matches so
    # the work stays proportional to literal/comment count.
    token_free = "a" * 262_144
    assert sql_lexing._COMMENT_ISOLATING_RE.findall(token_free) == []


def test_strip_comments_scales_to_query_string_cap() -> None:
    # 262144 is the QueryString model cap (service-2.json). The pre-sub
    # scanner measured ~92 ms here; the pass-through lands single-digit ms,
    # so 50 ms bounds it loosely while still failing the old shape.
    unit = "SELECT a, b FROM schema.table WHERE x = 'v' AND y > 1 "
    statement = (unit * (262_144 // len(unit) + 1))[:262_144]
    start = time.perf_counter()
    stripped = strip_comments(statement)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert stripped == statement
    assert elapsed_ms < 50
