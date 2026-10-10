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
   marks it Iceberg — and every item in a comma-separated list
   (``FROM a, b``) shares the anchor's walk, skipping ``(…)`` derived
   tables and ``ident(…)`` calls (``insert into`` is the exception: its
   ``(a,b)`` after the target is a column list, not a call). A bare
   ``from`` inside an ``ident(…)`` call's parens (``EXTRACT``/``TRIM``/
   ``SUBSTRING``/``OVERLAY`` arguments — call positions are measured by
   ``call_arg_positions``), closing ``IS [NOT] DISTINCT``, or ending a
   ``SHOW <objects> FROM`` spelling is skipped instead: those positions
   name values or schemas, never tables. Hive-bound references stay
   unqualified and resolve in the session's hive catalog — exactly the
   staged ``INSERT INTO iceberg SELECT`` and ``MERGE INTO iceberg USING
   hive_temp`` cross-catalog shapes awswrangler emits
   (``awswrangler/athena/_write_iceberg.py:411-426,871-877``).
3. The whole statement is backtick-normalized first
   (`` `ident` `` → ``"ident"``): Athena's DDL engine accepts backticks
   (which is why awswrangler emits them) but Trino's parser does not.
4. Probe verdicts cache across statements (``iceberg_probe``); any
   catalog-mutating statement — ``CREATE``/``ALTER``/``DROP``/``TRUNCATE`` —
   empties the cache since it may have changed a ``table_type`` marker.

The scan skips ``'…'`` literals and ``--``/``/* */`` comments so keywords or
references inside them are never rewritten, and dedupes Glue lookups per
(schema, table). Statements with no Iceberg involvement return None and
continue through the normal dialect path unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from athena_local.iceberg_probe import IcebergTableProbe
from athena_local.iceberg_table import (
    ICEBERG_CATALOG,
    iceberg_alter_ddl,
    iceberg_create_ddl,
)
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    SpanIndex,
    balanced_span,
    call_arg_positions,
    identifier_name,
    protected_spans,
    quoted_end,
    quoted_identifier,
    skip_ws,
    split_target,
    strip_comments,
    word_back,
)


def iceberg_trino_submission(
    query: str, database: str | None, probe: IcebergTableProbe
) -> str | None:
    """The Trino statement an Athena statement touching Iceberg maps to.

    Returns None when nothing applies — the statement continues through the
    normal dialect path with its original text.
    """
    normalized = _backtick_normalize(query)
    mapped = iceberg_create_ddl(normalized, database)
    if mapped is None:
        routed = _route_iceberg_references(normalized, database, probe)
        if routed is not None:
            mapped = iceberg_alter_ddl(routed)
    _invalidate_on_catalog_ddl(normalized, probe)
    return mapped


# Every catalog write the emulator can cause arrives as a submitted
# statement, and a leading ``create``/``alter``/``drop``/``truncate`` may
# have changed a ``table_type`` marker — so the probe's verdict map clears
# wholesale rather than resolving one name per mutation shape (RENAME
# targets, DROP DATABASE cascades, OR REPLACE all ride the same rule).
# Clearing runs only after the statement's own probes — a DROP still needs
# the cached verdict to route — and never on mapping raises, since a
# rejected statement mutates nothing. ``;``-joined tails match too.
_CATALOG_MUTATING = re.compile(
    r"(?i)(?:^|;)\s*(?:create|alter|drop|truncate)\b"
)


def _invalidate_on_catalog_ddl(query: str, probe: IcebergTableProbe) -> None:
    if _CATALOG_MUTATING.search(strip_comments(query)) is not None:
        probe.invalidate()


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

# Object words allowed between ``show`` and ``from`` when the argument is
# a schema/catalog, never a table: ``SHOW TABLES|SCHEMAS|DATABASES|VIEWS
# FROM``, plus Trino's ``SHOW FUNCTIONS|ROLES|ROLE GRANTS FROM``. Athena's
# ``SHOW COLUMNS FROM t`` is absent on purpose — its argument IS the
# table the probe must qualify.
_SHOW_FROM_NOUNS = frozenset(
    {
        "databases",
        "functions",
        "grants",
        "role",
        "roles",
        "schemas",
        "tables",
        "views",
    }
)


def _route_iceberg_references(
    query: str, database: str | None, probe: IcebergTableProbe
) -> str | None:
    """Qualify references whose (schema, table) the probe marks as Iceberg."""
    spans = protected_spans(query, quote_quoted=True)
    protected = SpanIndex(spans)
    # Only comments are skipped between list items — quoted identifiers and
    # literals stay visible since a quoted ident is a valid table ref.
    comments = SpanIndex([span for span in spans if query[span[0]] in "-/"])
    anchors, call_arg_froms = _anchor_scan(query, protected, comments)
    verified: dict[tuple[str, str], bool] = {}
    edits: list[tuple[int, int, str]] = []
    for anchor in anchors:
        word = anchor.group(0).lower()
        if word == "from" and _skipped_from(
            query, anchor.start(), comments, call_arg_froms
        ):
            continue
        # ``insert into`` alone keeps the plain first-item path — its
        # ``(a,b)`` after the target is a column list, not a call.
        first_item_call = word.split() != ["insert", "into"]
        for start, end in _table_item_refs(
            query, anchor.end(), comments, first_item_call
        ):
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
    query: str,
    start: int,
    comments: SpanIndex,
    first_item_call: bool,
) -> Iterator[tuple[int, int]]:
    """Ref spans in a comma-separated table-item list (``FROM a, b``).

    Every item is a table position: ``(SELECT …)`` derived tables are
    skipped whole (nested FROM lists anchor on their own ``from``), an
    ``ident(…)`` is a call (``UNNEST``/``LATERAL`` — never a Glue probe),
    and ``[AS] alias [(cols)]`` gaps separate items. The call skip covers
    the first item too unless ``first_item_call`` is off — ``insert
    into`` keeps the plain ``_REF`` path so ``INSERT INTO t (a,b)`` still
    probes ``t``.
    """
    pos = start
    chained = first_item_call
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
    query: str, pos: int, chained: bool, comments: SpanIndex
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


def _past_item_gap(query: str, pos: int, comments: SpanIndex) -> int:
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


def _past_noise(query: str, pos: int, comments: SpanIndex) -> int:
    """Index past whitespace and ``--``/``/* */`` comment spans."""
    while True:
        pos = skip_ws(query, pos)
        span = comments.covering(pos)
        if span is None:
            return pos
        pos = span[1]


def _schema_arg_from(query: str, start: int, comments: SpanIndex) -> bool:
    """Whether the bare ``from`` at ``start`` closes a ``SHOW <objects>``.

    ``SHOW TABLES|SCHEMAS|… FROM x`` takes a schema or catalog argument,
    so the anchor walk must not probe ``x``: probing rewrote ``SHOW
    TABLES FROM ice_t`` to ``iceberg."db"."ice_t"`` → ``Too many parts in
    schema name`` where AWS answers schema-not-found. ``SHOW COLUMNS FROM
    t`` is excluded deliberately (``columns`` is not a noun above) — its
    argument IS a table. A select item spelled ``show tables`` (column
    ``show``, alias ``tables``) is ruled out by the prefix check: only a
    statement boundary or an ``explain``/``from`` (``PREPARE … FROM
    SHOW``) word may precede the SHOW keyword.
    """
    word = word_back(query, start, comments)
    if word is None or word[0] not in _SHOW_FROM_NOUNS:
        return False
    pos = word[1]
    word = word_back(query, pos, comments)
    while word is not None and word[0] in _SHOW_FROM_NOUNS:
        pos = word[1]
        word = word_back(query, pos, comments)
    if word is None or word[0] != "show":
        return False
    prefix = word_back(query, word[1], comments)
    return prefix is None or prefix[0] in ("explain", "from")


def _anchor_scan(
    query: str, protected: SpanIndex, comments: SpanIndex
) -> tuple[list[re.Match[str]], frozenset[int]]:
    """Unprotected anchors + the bare ``from`` positions inside call parens.

    The call-paren scan is one O(n) pass, run only when a bare ``from``
    anchors at all — ``EXTRACT``/``TRIM``/``SUBSTRING``/``OVERLAY``
    arguments place a FROM keyword where no table list opens.
    """
    anchors = [
        anchor
        for anchor in _ANCHOR.finditer(query)
        if protected.covering(anchor.start()) is None
    ]
    call_arg_froms = (
        call_arg_positions(query, "from", protected, comments)
        if any(anchor.group(0).lower() == "from" for anchor in anchors)
        else frozenset[int]()
    )
    return anchors, call_arg_froms


def _skipped_from(
    query: str,
    start: int,
    comments: SpanIndex,
    call_arg_froms: frozenset[int],
) -> bool:
    """Whether the bare ``from`` at ``start`` never opens a table list.

    ``SHOW <objects> FROM x`` takes a schema argument, ``ident(… FROM …)``
    places it inside call args, and ``IS [NOT] DISTINCT FROM`` compares a
    value — none is a table position.
    """
    return (
        _schema_arg_from(query, start, comments)
        or start in call_arg_froms
        or _comparison_from(query, start, comments)
    )


def _comparison_from(query: str, start: int, comments: SpanIndex) -> bool:
    """Whether the bare ``from`` at ``start`` closes ``IS [NOT] DISTINCT``.

    ``a IS DISTINCT FROM b`` compares two value expressions — the ``b``
    is never a table, so a colliding Iceberg name must stay unprobed.
    """
    word = word_back(query, start, comments)
    if word is None or word[0] != "distinct":
        return False
    word = word_back(query, word[1], comments)
    if word is None:
        return False
    if word[0] == "is":
        return True
    if word[0] != "not":
        return False
    word = word_back(query, word[1], comments)
    return word is not None and word[0] == "is"


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


def _backtick_normalize(query: str) -> str:
    """`` `ident` `` → ``"ident"`` outside ``'…'`` literals and comments."""
    protected = protected_spans(query)
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
        close = quoted_end(query, index, "`")
        if close > end:
            break  # Unterminated backtick — leave the tail for Trino.
        out.append(query[segment:index])
        name = query[index + 1 : close - 1].replace("``", "`")
        out.append(f'"{quoted_identifier(name)}"')
        index = segment = close
    out.append(query[segment:end])
