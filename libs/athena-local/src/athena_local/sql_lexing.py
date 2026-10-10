"""SQL text primitives shared by the Athena→Trino statement rewrites.

The dialect modules scan statement text by hand — anchored regexes where a
single clause suffices, and these small lexers where balanced parentheses,
quoted literals (``''`` escapes), and identifier chains must not be broken
by a naive ``split``/regex (dialect.py, external_table.py, iceberg.py).
Nothing here is Athena- or Trino-specific.
"""

from __future__ import annotations

import re
from bisect import bisect_right

# One identifier chain segment: backticked, double-quoted, or bare.
# A double-quoted part may carry a ``""``-escaped quote
# (``"we""ird"``), SQL's standard identifier escape.
IDENTIFIER_PART = r"`[^`]+`|\"(?:[^\"]|\"\")+\"|[A-Za-z_][A-Za-z0-9_$]*"


def split_target(target: str) -> list[str]:
    """Split an identifier chain on dots outside backtick/double-quote spans.

    A quoted part may carry a literal dot (`` `my.db`.`t` ``), so a naive
    ``split(".")`` would shatter it.
    """
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in target:
        if char == "." and quote is None:
            parts.append("".join(current))
            current = []
            continue
        if char in '`"' and (quote is None or quote == char):
            quote = None if quote == char else char
        current.append(char)
    parts.append("".join(current))
    return parts


def identifier_name(part: str) -> str:
    """Unquote a chain segment; bare identifiers fold per Athena's rule."""
    part = part.strip()
    if len(part) >= 2 and part[0] == part[-1] and part[0] in '`"':
        unquoted = part[1:-1]
        # ``""`` is the standard quote escape inside a quoted identifier.
        return unquoted.replace('""', '"') if part[0] == '"' else unquoted
    return part.lower()


def sql_literal(value: str) -> str:
    """``'``-escape a value for use inside a SQL string literal."""
    return value.replace("'", "''")


def quoted_identifier(name: str) -> str:
    """``"``-escape a name for use inside a quoted Trino identifier."""
    return name.replace('"', '""')


def literal_value(raw: str | None) -> str | None:
    """The unescaped text inside a ``'…'`` literal; None if not a literal."""
    if raw is None or len(raw) < 2 or raw[0] != "'" or raw[-1] != "'":
        return None
    return raw[1:-1].replace("''", "'")


def split_top_level(text: str) -> list[str]:
    """Split on commas outside strings and brackets (``ARRAY['a','b']``)."""
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            string = string_end(text, index)
            if string is None:
                break
            current.append(text[index:string])
            index = string
            continue
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    parts.append("".join(current))
    return parts


def balanced_span(text: str, start: int) -> int | None:
    """Index just past the ``)`` closing ``text[start]``; None if unbalanced.

    String literals (with ``''`` escapes) are skipped verbatim so parens
    inside them cannot skew the depth.
    """
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "'":
            string = string_end(text, index)
            if string is None:
                return None
            index = string
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def string_end(text: str, start: int) -> int | None:
    """Index just past the ``'``-quoted literal at ``start``; None if unterminated."""
    return _quoted_scan(text, start, "'")


def quoted_end(text: str, start: int, quote: str) -> int:
    """Index just past the ``quote``-quoted span at ``start``.

    Unlike ``string_end``, an unterminated span returns ``len(text)`` —
    callers that swallow the tail (placeholder binding, backtick
    normalization) use this contract.
    """
    end = _quoted_scan(text, start, quote)
    return end if end is not None else len(text)


def _quoted_scan(text: str, start: int, quote: str) -> int | None:
    """Shared scan core: doubled ``quote`` escapes (``''``/``""``) skip."""
    cursor = start + 1
    while cursor < len(text):
        if text[cursor] != quote:
            cursor += 1
            continue
        if text[cursor + 1 : cursor + 2] == quote:
            cursor += 2
            continue
        return cursor + 1
    return None


_QUOTED_PAIR = re.compile(r"^\s*'((?:[^']|'')*)'\s*=\s*'((?:[^']|'')*)'\s*$")


def quoted_pair(pair: str) -> tuple[str, str] | None:
    """A ``'key' = 'value'`` TBLPROPERTIES-style pair → decoded parts."""
    match = _QUOTED_PAIR.match(pair)
    if match is None:
        return None
    return (
        match.group(1).replace("''", "'"),
        match.group(2).replace("''", "'"),
    )


def skip_ws(text: str, index: int) -> int:
    """Index of the first non-whitespace character at or after ``index``."""
    while index < len(text) and text[index] in " \t\n\r":
        index += 1
    return index


# Alternation order is load-bearing: a string literal is matched whole
# (including its ``''`` escapes) before any comment marker inside it, so
# ``'-- x'`` or ``'/* x */'`` text cannot masquerade as a comment. An
# unterminated ``/*`` swallows to end of input. There is deliberately no
# per-character fallback: text matching none of the alternatives passes
# ``sub`` through untouched, keeping the scan proportional to the token
# count rather than the input length.
_COMMENT_ISOLATING_RE = re.compile(
    r"'(?:[^']|'')*'|--[^\n]*|/\*.*?\*/|/\*.*",
    re.DOTALL,
)


def strip_comments(sql: str) -> str:
    """Drop ``--`` and ``/* */`` comments outside string literals."""
    return _COMMENT_ISOLATING_RE.sub(_drop_comment, sql)


def _drop_comment(match: re.Match[str]) -> str:
    """Empty string for comment matches; literals re-insert verbatim."""
    token = match.group(0)
    return "" if token.startswith(("--", "/*")) else token


class SpanIndex:
    """O(log n) covering-span lookup over one statement's ordered spans.

    ``protected_spans`` emits left-to-right and the comment filter keeps
    that order, so a parallel start list answers ``covering`` by bisect.
    The previous index-0 rescan per call made the item walk
    O(refs × comments) — 32.6 s measured at 10k comments where plain refs
    stayed at 248 ms (iceberg routing, 2026-10-07).
    """

    def __init__(self, spans: list[tuple[int, int]]) -> None:
        ordered = sorted(spans)
        self._spans = ordered
        self._starts = [start for start, _ in ordered]

    def covering(self, position: int) -> tuple[int, int] | None:
        index = bisect_right(self._starts, position) - 1
        if index < 0:
            return None
        span = self._spans[index]
        return span if position < span[1] else None


def protected_spans(
    query: str, quote_quoted: bool = False
) -> list[tuple[int, int]]:
    """Literal/comment/identifier spans a scan must never rewrite inside of.

    ``'…'`` literals, ``--``/``/* */`` comments, and ``"…"``-quoted
    identifiers always protect their contents — a ``'`` or a keyword
    inside ``"don`t"``/``"from"`` is identifier text, not syntax.
    `` `` ``-quoted names protect only when ``quote_quoted``: the route
    scan must not treat `` `from` `` as a FROM anchor, but the backtick
    normalizer needs those spans visible to convert them.
    """
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(query):
        index = _span_step(query, index, spans, quote_quoted)
    return spans


def _span_step(
    query: str,
    index: int,
    spans: list[tuple[int, int]],
    quote_quoted: bool,
) -> int:
    char = query[index]
    if char == "'":
        return _literal_step(query, index, spans)
    if char in '"`':
        return _identifier_step(query, index, char, spans, quote_quoted)
    if query[index : index + 2] == "--":
        return _comment_step(query, index, "\n", spans)
    if query[index : index + 2] == "/*":
        return _comment_step(query, index, "*/", spans)
    return index + 1


def _literal_step(query: str, index: int, spans: list[tuple[int, int]]) -> int:
    end = string_end(query, index)
    if end is None:
        return len(query)
    spans.append((index, end))
    return end


def _identifier_step(
    query: str,
    index: int,
    char: str,
    spans: list[tuple[int, int]],
    quote_quoted: bool,
) -> int:
    end = quoted_end(query, index, char)
    if char == '"' or quote_quoted:
        spans.append((index, end))
    return end


def _comment_step(
    query: str,
    index: int,
    terminator: str,
    spans: list[tuple[int, int]],
) -> int:
    end = query.find(terminator, index + 2)
    if end == -1:
        end = len(query)
    elif terminator == "*/":
        end += 2
    spans.append((index, end))
    return end


def word_back(
    query: str, pos: int, comments: SpanIndex
) -> tuple[str, int] | None:
    """(lowercased word, start) of the bare identifier ending before ``pos``.

    Quote/dot/punctuation characters are not word characters, so
    ``'x'``, ``"show"``, and ``show.tables`` all stop the scan — only a
    whitespace/comment-separated bare word is returned.
    """
    end = _noise_back(query, pos, comments)
    start = end
    while start > 0 and query[start - 1] in _WORD_CHARS:
        start -= 1
    if start == end:
        return None
    return query[start:end].lower(), start


def _noise_back(query: str, pos: int, comments: SpanIndex) -> int:
    """Index before whitespace and comment spans, scanning backwards."""
    while True:
        while pos > 0 and query[pos - 1] in " \t\n\r":
            pos -= 1
        span = comments.covering(pos - 1)
        if span is None:
            return pos
        pos = span[0]


# Identifiers continue on ``[A-Za-z0-9_$]`` (IDENTIFIER_PART's tail); the
# backward scan needs the whole word so ``xtables`` never suffix-matches
# a SHOW noun.
_WORD_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$"
)


# Words after which ``(`` may wrap a query or a scalar-subquery-bearing
# expression — never a function call — so a ``from`` inside still anchors
# a table position (``IN (``, ``EXISTS (``, CTE ``AS (``, ``UNLOAD (``,
# set-operation arms, boolean/scalar-subquery contexts). Anything else
# preceding ``(`` is a call open.
_QUERY_PAREN_WORDS = frozenset(
    {
        "all",
        "and",
        "any",
        "as",
        "between",
        "by",
        "case",
        "distinct",
        "else",
        "escape",
        "except",
        "exists",
        "explain",
        "from",
        "having",
        "ilike",
        "in",
        "intersect",
        "join",
        "lateral",
        "like",
        "not",
        "on",
        "or",
        "rlike",
        "select",
        "some",
        "then",
        "to",
        "union",
        "unload",
        "using",
        "values",
        "when",
        "where",
    }
)


def call_arg_positions(
    query: str,
    keyword: str,
    protected: SpanIndex,
    comments: SpanIndex,
) -> frozenset[int]:
    """Positions where a bare ``keyword`` sits inside ``ident(…)`` call args.

    ``EXTRACT(year FROM ts)``/``TRIM('x' FROM s)`` place a keyword inside
    call parens where it never opens the clause it names elsewhere. The
    innermost enclosing ``(`` is a function call exactly when a bare word
    precedes it that is not a query-context keyword
    (``_QUERY_PAREN_WORDS``); an expression ``(`` or a derived table
    keeps the keyword live — ``f((SELECT … FROM t))`` still anchors.
    """
    bare = re.compile(rf"(?i)\b{re.escape(keyword)}\b")
    positions: set[int] = set()
    calls: list[bool] = []  # One flag per open ``(``: True for a call.
    pos = 0
    while pos < len(query):
        span = protected.covering(pos)
        if span is not None:
            pos = span[1]
            continue
        char = query[pos]
        if char == "(":
            calls.append(_opens_call(query, pos, comments))
        elif char == ")":
            if calls:
                calls.pop()
        elif calls and calls[-1] and bare.match(query, pos) is not None:
            positions.add(pos)
        pos += 1
    return frozenset(positions)


def _opens_call(query: str, pos: int, comments: SpanIndex) -> bool:
    """Whether the ``(`` at ``pos`` opens ``ident(…)`` call args."""
    word = word_back(query, pos, comments)
    return word is not None and word[0] not in _QUERY_PAREN_WORDS
