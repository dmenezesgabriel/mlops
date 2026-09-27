"""Athena Iceberg DDL → the dedicated ``iceberg`` Trino catalog's grammar.

Athena declares an Iceberg table through
``CREATE TABLE … TBLPROPERTIES('table_type'='ICEBERG')`` (AWS UG
``querying-iceberg-creating-tables.html``) and runs schema evolution through
Hive-flavored ``ALTER TABLE … ADD COLUMNS`` / ``CHANGE COLUMN`` — the shapes
awswrangler emits (``awswrangler/athena/_write_iceberg.py:108-113,246,258``).
Trino's Iceberg connector instead wants ``CREATE TABLE … WITH(format,
location[, partitioning])`` and one action per ALTER, so this module maps:

* CREATE: clause-by-clause → ``iceberg."db"."t"`` + WITH properties; column
  types via ``hive_types`` and the ``bucket(N, col)`` / ``truncate(N, col)``
  partition transforms re-ordered to Trino's ``(col, N)`` spelling (probed:
  the coordinator rejects Athena's order with INVALID_TABLE_PROPERTY).
* ALTER on an already iceberg-qualified target: single-column
  ``ADD COLUMNS`` → ``ADD COLUMN``, ``CHANGE COLUMN c c type`` →
  ``ALTER COLUMN c SET DATA TYPE``; multi-column or rename forms raise
  ``InvalidRequestException`` — one submission cannot carry two actions.

``format_version`` stays at Trino's default (2), matching Athena's "Iceberg
v2 tables" guarantee; the Athena-only TBLPROPERTIES hints
(``write_compression``, ``optimize_*``, ``vacuum_*``) are accepted and
dropped — none maps to a Trino WITH or per-statement session property on
the iceberg catalog (probed ``SHOW SESSION``).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from athena_local.errors import InvalidRequestException
from athena_local.hive_types import (
    HiveColumn,
    hive_column_defs,
    hive_type_to_trino,
)
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    balanced_span,
    identifier_name,
    quoted_identifier,
    quoted_pair,
    skip_ws,
    split_target,
    split_top_level,
    sql_literal,
    string_end,
)

ICEBERG_CATALOG = "iceberg"
ICEBERG_TABLE_TYPE = "ICEBERG"

# The Iceberg keys AWS accepts in TBLPROPERTIES (AWS UG "only a predefined
# list"); ``table_type`` is the routing signal and the rest either map to a
# Trino WITH property or are engine-side hints Trino drops.
_ATHENA_ICEBERG_TBLPROPERTIES = frozenset(
    {
        "table_type",
        "format",
        "write_compression",
        "optimize_rewrite_data_file_threshold",
        "optimize_rewrite_delete_file_threshold",
        "vacuum_min_snapshots_to_keep",
        "vacuum_max_snapshot_age_seconds",
        "vacuum_max_metadata_files_to_keep",
        "write_data_path_enabled",
    }
)
_ICEBERG_FORMATS = {"parquet": "PARQUET", "orc": "ORC", "avro": "AVRO"}

_HEAD = re.compile(r"(?i)^(?P<prefix>\s*)create\s+table\b")
_IF_NOT_EXISTS = re.compile(r"(?i)\s*if\s+not\s+exists\b")
_TARGET = re.compile(
    rf"\s*(?P<target>(?:{IDENTIFIER_PART})(?:\s*\.\s*(?:{IDENTIFIER_PART}))*)"
)
_TAIL_END = re.compile(r"\s*;?\s*")
_CLAUSE_WORD = re.compile(r"(?i)\s*([A-Za-z_]+)")
_PARTITIONED_BY = re.compile(r"(?i)\s*partitioned\s+by\s*\(")
_TBLPROPERTIES = re.compile(r"(?i)\s*tblproperties\s*\(")
_TWO_ARG_TRANSFORM = re.compile(
    r"(?i)^\s*(bucket|truncate)\s*\(\s*(\d+)\s*,\s*(.+?)\s*\)\s*$"
)


def iceberg_create_ddl(query: str, database: str | None) -> str | None:
    """``CREATE TABLE … table_type=ICEBERG`` → the iceberg catalog's CREATE.

    Example::

        iceberg_create_ddl(
            'CREATE TABLE `t` (`id` bigint) LOCATION \\'s3://b/t/\\' '
            'TBLPROPERTIES (\\'table_type\\'=\\'ICEBERG\\')', 'db'
        )
        # → 'CREATE TABLE iceberg."db"."t" ("id" bigint)
        #    WITH (format=\\'PARQUET\\', location=\\'s3://b/t/\\')'
    """
    head = _HEAD.match(query)
    if head is None:
        return None
    parsed = _parse(query, head.end(), head.group("prefix"))
    if parsed is None or not parsed.iceberg_declared:
        return None
    return _emit_create(parsed, database)


def iceberg_alter_ddl(query: str) -> str:
    """Hive's ``ADD COLUMNS``/``CHANGE COLUMN`` on an iceberg-qualified target.

    Input is the post-routing statement; only ``ALTER TABLE iceberg.…``
    shapes convert. Example::

        iceberg_alter_ddl(
            'ALTER TABLE iceberg."db"."t" ADD COLUMNS ("w" double)'
        )
        # → 'ALTER TABLE iceberg."db"."t" ADD COLUMN "w" double'
    """
    head = _ALTER_ICEBERG.match(query)
    if head is None:
        return query
    name = head.group("name")
    add = _ALTER_ADD_COLUMNS.match(query, head.end())
    if add is not None:
        return _alter_add_columns(query, name, add)
    change = _ALTER_CHANGE_COLUMN.match(query, head.end())
    if change is not None:
        return _alter_change_column(query, name, change)
    return query


@dataclass
class _IcebergCreate:
    """The parsed pieces of an Athena Iceberg ``CREATE TABLE``."""

    prefix: str
    if_not_exists: bool = False
    schema: str | None = None
    table: str = ""
    columns: list[HiveColumn] = field(default_factory=list)
    partition_entries: list[str] = field(default_factory=list)
    table_comment: str | None = None  # raw 'lit' literal
    location: str | None = None  # raw 'lit' literal
    format_name: str | None = None
    iceberg_declared: bool = False


def _parse(query: str, cursor: int, prefix: str) -> _IcebergCreate | None:
    """The clause loop — each matcher emits its clause or None (pass-through)."""
    acc = _IcebergCreate(prefix=prefix)
    end = _parse_head(query, cursor, acc)
    if end is None:
        return None
    while _TAIL_END.fullmatch(query[end:]) is None:
        matched = _match_clause(query, end, acc)
        if matched is None:
            return None
        end = matched
    return acc


def _parse_head(query: str, cursor: int, acc: _IcebergCreate) -> int | None:
    exists = _IF_NOT_EXISTS.match(query, cursor)
    if exists is not None:
        acc.if_not_exists = True
        cursor = exists.end()
    target = _TARGET.match(query, cursor)
    if target is None:
        return None
    parts = [identifier_name(p) for p in split_target(target.group("target"))]
    if len(parts) not in (1, 2):
        # 3+-part (hive.db.t) — leave the shape for Trino to reject.
        return None
    if len(parts) == 2:
        acc.schema, acc.table = parts[0], parts[1]
    elif len(parts) == 1:
        acc.table = parts[0]
    cursor = skip_ws(query, target.end())
    if query[cursor : cursor + 1] != "(":
        return cursor  # No column list — tail clauses still parse.
    end = balanced_span(query, cursor)
    if end is None:
        return None
    columns = hive_column_defs(query[cursor + 1 : end - 1])
    if columns is None:
        return None
    acc.columns = columns
    return end


def _match_clause(query: str, cursor: int, acc: _IcebergCreate) -> int | None:
    word = _CLAUSE_WORD.match(query, cursor)
    if word is None:
        return None
    matcher = _CLAUSE_MATCHERS.get(word.group(1).lower())
    if matcher is None:
        return None
    return matcher(query, cursor, acc)


def _literal_matcher(
    pattern: re.Pattern[str], attribute: str
) -> Callable[[str, int, _IcebergCreate], int | None]:
    """Clause matcher assigning a single ``'lit'`` literal to ``attribute``."""

    def match(query: str, cursor: int, acc: _IcebergCreate) -> int | None:
        clause = pattern.match(query, cursor)
        if clause is None:
            return None
        end = string_end(query, clause.end() - 1)
        if end is None:
            return None
        setattr(acc, attribute, query[clause.end() - 1 : end])
        return end

    return match


def _match_partitioned_by(
    query: str, cursor: int, acc: _IcebergCreate
) -> int | None:
    match = _PARTITIONED_BY.match(query, cursor)
    if match is None:
        return None
    end = balanced_span(query, match.end() - 1)
    if end is None:
        return None
    entries = [
        entry.strip()
        for entry in split_top_level(query[match.end() : end - 1])
    ]
    if not entries or any(not entry for entry in entries):
        return None
    acc.partition_entries = entries
    return end


def _match_tblproperties(
    query: str, cursor: int, acc: _IcebergCreate
) -> int | None:
    match = _TBLPROPERTIES.match(query, cursor)
    if match is None:
        return None
    end = balanced_span(query, match.end() - 1)
    if end is None:
        return None
    pairs: dict[str, str] = {}
    for pair in split_top_level(query[match.end() : end - 1]):
        if not pair.strip():
            continue
        kv = quoted_pair(pair)
        if kv is None:
            return None
        pairs[kv[0].lower()] = kv[1]
    acc.iceberg_declared = (
        pairs.get("table_type", "").upper() == ICEBERG_TABLE_TYPE
    )
    if acc.iceberg_declared:
        _apply_iceberg_tblproperties(pairs, acc)
    return end


def _apply_iceberg_tblproperties(
    pairs: dict[str, str], acc: _IcebergCreate
) -> None:
    """Validate the declared-Iceberg property set; drop what Trino can't take."""
    for key, value in pairs.items():
        if key == "table_type":
            continue
        if key not in _ATHENA_ICEBERG_TBLPROPERTIES:
            raise InvalidRequestException(
                f"TBLPROPERTIES key {key!r} is not in Athena's Iceberg "
                f"table property list; expected one of "
                f"{sorted(_ATHENA_ICEBERG_TBLPROPERTIES)}"
            )
        if key == "format":
            acc.format_name = _iceberg_format(value)


def _iceberg_format(value: str) -> str:
    fmt = _ICEBERG_FORMATS.get(value.lower())
    if fmt is None:
        raise InvalidRequestException(
            f"Iceberg 'format' value {value!r} is not supported; expected "
            f"one of {sorted(_ICEBERG_FORMATS)}"
        )
    return fmt


def _emit_create(acc: _IcebergCreate, database: str | None) -> str | None:
    schema = acc.schema or database
    if schema is None or not acc.columns:
        return None  # Unresolvable/shape-less input falls through to Trino.
    if acc.location is None:
        raise InvalidRequestException(
            "Iceberg CREATE TABLE requires LOCATION 's3://…' — the emulator "
            "has no default warehouse location to fall back to"
        )
    if_not_exists = "IF NOT EXISTS " if acc.if_not_exists else ""
    name = (
        f'{ICEBERG_CATALOG}."{quoted_identifier(schema)}".'
        f'"{quoted_identifier(acc.table)}"'
    )
    columns = ", ".join(column.sql for column in acc.columns)
    comment = f" COMMENT {acc.table_comment}" if acc.table_comment else ""
    return (
        f"{acc.prefix}CREATE TABLE {if_not_exists}{name} ({columns})"
        f"{comment} WITH ({', '.join(_with_properties(acc))})"
    )


def _with_properties(acc: _IcebergCreate) -> list[str]:
    properties = [
        f"format='{acc.format_name or 'PARQUET'}'",
        f"location={acc.location}",
    ]
    if acc.partition_entries:
        entries = ",".join(
            f"'{sql_literal(_partition_entry(entry))}'"
            for entry in acc.partition_entries
        )
        properties.append(f"partitioning=ARRAY[{entries}]")
    return properties


def _partition_entry(entry: str) -> str:
    """Athena's ``bucket(N, col)``/``truncate(N, col)`` → Trino ``(col, N)``."""
    transform = _TWO_ARG_TRANSFORM.match(entry)
    if transform is None:
        return entry
    return (
        f"{transform.group(1).lower()}"
        f"({transform.group(3)}, {transform.group(2)})"
    )


_ALTER_ICEBERG = re.compile(
    rf"(?i)^\s*alter\s+table\s+(?P<name>{ICEBERG_CATALOG}\."
    rf"(?:{IDENTIFIER_PART})(?:\s*\.\s*(?:{IDENTIFIER_PART}))?)\s*"
)
_ALTER_ADD_COLUMNS = re.compile(r"(?i)add\s+columns\s*\(")
_ALTER_CHANGE_COLUMN = re.compile(
    rf"(?i)change\s+column\s+(?P<old>{IDENTIFIER_PART})\s+"
    rf"(?P<new>{IDENTIFIER_PART})\s+(?P<ctype>.+?)\s*;?\s*$"
)


def _alter_add_columns(query: str, name: str, add: re.Match[str]) -> str:
    end = balanced_span(query, add.end() - 1)
    if end is None or _TAIL_END.fullmatch(query[end:]) is None:
        return query
    columns = hive_column_defs(query[add.end() : end - 1])
    if not columns:
        return query
    if len(columns) > 1:
        raise InvalidRequestException(
            "ALTER TABLE … ADD COLUMNS with multiple columns is not "
            "supported; Trino allows one action per ALTER TABLE — submit "
            "one ADD COLUMNS statement per new column"
        )
    return f"ALTER TABLE {name} ADD COLUMN {columns[0].sql}"


def _alter_change_column(query: str, name: str, change: re.Match[str]) -> str:
    old = identifier_name(change.group("old"))
    new = identifier_name(change.group("new"))
    if old != new:
        raise InvalidRequestException(
            "ALTER TABLE … CHANGE COLUMN with a renamed column is not "
            "supported; Trino needs separate RENAME and SET DATA TYPE "
            "actions — submit them as two statements"
        )
    trino_type = hive_type_to_trino(change.group("ctype"))
    if trino_type is None:
        return query  # Unparseable type rides to Trino for its own error.
    return (
        f"ALTER TABLE {name} ALTER COLUMN "
        f'"{quoted_identifier(new)}" SET DATA TYPE {trino_type}'
    )


_CLAUSE_MATCHERS: dict[
    str, Callable[[str, int, _IcebergCreate], int | None]
] = {
    "partitioned": _match_partitioned_by,
    "comment": _literal_matcher(
        re.compile(r"(?i)\s*comment\s*'"), "table_comment"
    ),
    "location": _literal_matcher(
        re.compile(r"(?i)\s*location\s*'"), "location"
    ),
    "tblproperties": _match_tblproperties,
}
