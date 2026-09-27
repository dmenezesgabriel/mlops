"""SQL text primitives shared by the Athena→Trino statement rewrites.

The dialect modules scan statement text by hand — anchored regexes where a
single clause suffices, and these small lexers where balanced parentheses,
quoted literals (``''`` escapes), and identifier chains must not be broken
by a naive ``split``/regex (dialect.py, external_table.py, iceberg.py).
Nothing here is Athena- or Trino-specific.
"""

from __future__ import annotations

import re

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
# unterminated ``/*`` swallows to end of input.
_COMMENT_ISOLATING_RE = re.compile(
    r"'(?:[^']|'')*'|--[^\n]*|/\*.*?\*/|/\*.*|.",
    re.DOTALL,
)


def strip_comments(sql: str) -> str:
    """Drop ``--`` and ``/* */`` comments outside string literals."""
    kept: list[str] = []
    for match in _COMMENT_ISOLATING_RE.finditer(sql):
        token = match.group(0)
        if not token.startswith(("--", "/*")):
            kept.append(token)
    return "".join(kept)
