"""Iceberg statement routing — which statements run on the ``iceberg`` catalog.

Athena registers Iceberg tables in Glue with
``Parameters.table_type=ICEBERG`` (AWS UG
``querying-iceberg-creating-tables.html``) and transparently routes
statements touching them to its Iceberg engine; the hive catalog's view of
such a table fails ``UNSUPPORTED_TABLE_TYPE`` (probed on the compose
stack). The emulator mirrors the split with a second Trino catalog over the
same moto Glue metastore — ``iceberg_table.py`` maps the DDL
(``iceberg_create_ddl``/``iceberg_alter_ddl``) and this module decides what
reaches it:

1. ``CREATE TABLE … TBLPROPERTIES('table_type'='ICEBERG')`` → the iceberg
   catalog's CREATE (self-declared; no Glue read needed).
2. Every other statement gets each ``insert into``/``merge into``/
   ``delete from``/``alter table``/``drop``/``describe``/``from``/
   ``join``/``using``-anchored table reference qualified
   ``iceberg."schema"."table"`` when a Glue ``table_type`` lookup (``probe``)
   marks it Iceberg — and every later item in a comma-separated list
   (``FROM a, b``) shares the anchor's walk, skipping ``(…)`` derived
   tables and ``ident(…)`` calls. Hive-bound references stay unqualified
   and resolve in the session's hive catalog — exactly the staged
   ``INSERT INTO iceberg SELECT`` and ``MERGE INTO iceberg USING
   hive_temp`` cross-catalog shapes awswrangler emits
   (``awswrangler/athena/_write_iceberg.py:411-426,871-877``).
3. The whole statement is backtick-normalized first
   (`` `ident` `` → ``"ident"``): Athena's DDL engine accepts backticks
   (which is why awswrangler emits them) but Trino's parser does not.

The scan skips ``'…'`` literals and ``--``/``/* */`` comments so keywords or
references inside them are never rewritten, and dedupes Glue lookups per
(schema, table). Statements with no Iceberg involvement return None and
continue through the normal dialect path unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Protocol

from athena_local.errors import MetadataException
from athena_local.glue_proxy import GlueProxy
from athena_local.iceberg_table import (
    ICEBERG_CATALOG,
    ICEBERG_TABLE_TYPE,
    iceberg_alter_ddl,
    iceberg_create_ddl,
)
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    balanced_span,
    identifier_name,
    quoted_identifier,
    skip_ws,
    split_target,
    string_end,
)


class IcebergTableProbe(Protocol):
    """Whether a Glue table is Iceberg (the ``table_type`` marker)."""

    def is_iceberg_table(self, database: str, table: str) -> bool: ...


class GlueIcebergProbe:
    """Iceberg detection over moto Glue's ``Parameters`` map.

    Trino's Iceberg Glue registration writes ``table_type=ICEBERG`` plus the
    current ``metadata_location`` — the same marker AWS's Iceberg Glue
    integrations record — so a shared Glue read answers the routing
    question for tables created through either engine.

    Example::

        probe = GlueIcebergProbe(glue_proxy)
        probe.is_iceberg_table("analytics", "ice_t")  # True when Glue
        # Parameters carry table_type=ICEBERG, else False.
    """

    def __init__(self, glue: GlueProxy) -> None:
        self._glue = glue

    def is_iceberg_table(self, database: str, table: str) -> bool:
        try:
            metadata = self._glue.get_table(database, table)
        except MetadataException:
            return False
        parameters = metadata.parameters or {}
        return parameters.get("table_type", "").upper() == ICEBERG_TABLE_TYPE


def iceberg_trino_submission(
    query: str, database: str | None, probe: IcebergTableProbe
) -> str | None:
    """The Trino statement an Athena statement touching Iceberg maps to.

    Returns None when nothing applies — the statement continues through the
    normal dialect path with its original text.
    """
    normalized = _backtick_normalize(query)
    created = iceberg_create_ddl(normalized, database)
    if created is not None:
        return created
    routed = _route_iceberg_references(normalized, database, probe)
    if routed is None:
        return None
    return iceberg_alter_ddl(routed)


# Statement-leading keywords after which a table reference may appear;
# ``from``/``join``/``using``/``update`` cover every position (subqueries
# included), so consumer DML routes regardless of statement shape.
_ANCHOR = re.compile(
    r"(?i)\b(?:insert\s+into|merge\s+into|delete\s+from|alter\s+table"
    r"|truncate\s+table|drop\s+table|show\s+create\s+table|describe"
    r"|update|using|join|from)\b"
)
_REF = re.compile(
    rf"\s*(?P<ref>(?:{IDENTIFIER_PART})"
    rf"(?:\s*\.\s*(?:{IDENTIFIER_PART})){{0,2}})"
)


def _route_iceberg_references(
    query: str, database: str | None, probe: IcebergTableProbe
) -> str | None:
    """Qualify references whose (schema, table) the probe marks as Iceberg."""
    protected = _protected_spans(query, quote_quoted=True)
    # Only comments are skipped between list items — quoted identifiers and
    # literals stay visible since a quoted ident is a valid table ref.
    comments = [s for s in protected if query[s[0]] in "-/"]
    verified: dict[tuple[str, str], bool] = {}
    edits: list[tuple[int, int, str]] = []
    for anchor in _ANCHOR.finditer(query):
        if _inside(protected, anchor.start()):
            continue
        for start, end in _table_item_refs(query, anchor.end(), comments):
            _route_ref(query, start, end, database, probe, verified, edits)
    if not edits:
        return None
    for start, end, replacement in sorted(edits, reverse=True):
        query = query[:start] + replacement + query[end:]
    return query


def _route_ref(
    query: str,
    start: int,
    end: int,
    database: str | None,
    probe: IcebergTableProbe,
    verified: dict[tuple[str, str], bool],
    edits: list[tuple[int, int, str]],
) -> None:
    resolved = _resolve(query[start:end], database)
    if resolved is None:
        return
    schema, table = resolved
    key = (schema.lower(), table.lower())
    if key not in verified:
        verified[key] = probe.is_iceberg_table(schema, table)
    if not verified[key]:
        return
    edits.append((start, end, _iceberg_qualified(schema, table)))


_AS = re.compile(r"(?i)as\b")


def _table_item_refs(
    query: str, start: int, comments: list[tuple[int, int]]
) -> Iterator[tuple[int, int]]:
    """Ref spans in a comma-separated table-item list (``FROM a, b``).

    Every item is a table position: ``(SELECT …)`` derived tables are
    skipped whole (nested FROM lists anchor on their own ``from``), a
    chained ``ident(…)`` is a call (``UNNEST``/``LATERAL`` — never a Glue
    probe), and ``[AS] alias [(cols)]`` gaps separate items. The first
    item keeps the plain ``_REF`` path so ``INSERT INTO t (a,b)`` still
    probes ``t`` — its ``(a,b)`` is a column list, not a call.
    """
    pos = start
    chained = False
    while True:
        pos = _past_noise(query, pos, comments)
        ref, pos = _scan_item(query, pos, chained, comments)
        if pos is None:
            return
        if ref is not None:
            yield ref
        pos = _past_item_gap(query, pos, comments)
        if pos >= len(query) or query[pos] != ",":
            return
        pos += 1
        chained = True


def _scan_item(
    query: str, pos: int, chained: bool, comments: list[tuple[int, int]]
) -> tuple[tuple[int, int] | None, int | None]:
    """One item at ``pos`` → (ref span, item end); ``end`` None stops."""
    if pos >= len(query):
        return None, None
    if query[pos] == "(":
        return None, balanced_span(query, pos)
    ref = _REF.match(query, pos)
    if ref is None:
        return None, None
    after = _past_noise(query, ref.end(), comments)
    if chained and after < len(query) and query[after] == "(":
        return None, balanced_span(query, after)
    return ref.span("ref"), ref.end()


def _past_item_gap(
    query: str, pos: int, comments: list[tuple[int, int]]
) -> int:
    """Index after ``[AS] alias [(cols)]`` — where a ``,`` may sit.

    The one-identifier bound is the safety stop: ``GROUP BY a, b`` and
    ``SET a = 1, b = 2`` commas stay untouched because ``GROUP``/``SET``
    fills the alias slot and the following token is never ``,``.
    """
    pos = _past_noise(query, pos, comments)
    match = _AS.match(query, pos)
    if match is not None:
        pos = _past_noise(query, match.end(), comments)
    name = _REF.match(query, pos)
    if name is not None:
        pos = _past_noise(query, name.end(), comments)
    if pos < len(query) and query[pos] == "(":
        end = balanced_span(query, pos)
        if end is not None:
            pos = end
    return _past_noise(query, pos, comments)


def _past_noise(query: str, pos: int, comments: list[tuple[int, int]]) -> int:
    """Index past whitespace and ``--``/``/* */`` comment spans."""
    while True:
        pos = skip_ws(query, pos)
        end = _covering_end(comments, pos)
        if end is None:
            return pos
        pos = end


def _covering_end(spans: list[tuple[int, int]], position: int) -> int | None:
    for start, end in spans:
        if start <= position < end:
            return end
    return None


def _resolve(reference: str, database: str | None) -> tuple[str, str] | None:
    parts = [identifier_name(p) for p in split_target(reference)]
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1 and database is not None:
        return database, parts[0]
    return None  # 3-part (already cataloged) or no schema context.


def _iceberg_qualified(schema: str, table: str) -> str:
    return (
        f'{ICEBERG_CATALOG}."{quoted_identifier(schema)}".'
        f'"{quoted_identifier(table)}"'
    )


def _protected_spans(
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
    end = _quoted_end(query, index, char)
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


def _quoted_end(query: str, start: int, quote: str) -> int:
    """Index past the closing ``quote``; doubled-quote escapes are skipped."""
    cursor = start + 1
    while cursor < len(query):
        if query[cursor] != quote:
            cursor += 1
            continue
        if query[cursor + 1 : cursor + 2] == quote:
            cursor += 2
            continue
        return cursor + 1
    return len(query)


def _inside(spans: list[tuple[int, int]], position: int) -> bool:
    return _covering_end(spans, position) is not None


def _backtick_normalize(query: str) -> str:
    """`` `ident` `` → ``"ident"`` outside ``'…'`` literals and comments."""
    protected = _protected_spans(query)
    out: list[str] = []
    index = 0
    for start, end in protected:
        _emit_backticks(query, index, start, out)
        out.append(query[start:end])
        index = end
    _emit_backticks(query, index, len(query), out)
    return "".join(out)


def _emit_backticks(query: str, start: int, end: int, out: list[str]) -> None:
    """Convert `` `…` `` spans inside ``[start, end)`` to ``"…"``-quoted."""
    index = start
    segment = start
    while index < end:
        if query[index] != "`":
            index += 1
            continue
        close = _quoted_end(query, index, "`")
        if close > end:
            break  # Unterminated backtick — leave the tail for Trino.
        out.append(query[segment:index])
        name = query[index + 1 : close - 1].replace("``", "`")
        out.append(f'"{quoted_identifier(name)}"')
        index = segment = close
    out.append(query[segment:end])
