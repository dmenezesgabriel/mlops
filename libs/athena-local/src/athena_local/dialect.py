"""Athena-to-Trino statement dialect map.

Real Athena parses a slightly wider SQL vocabulary than the Trino 483 engine
underneath this emulator. The Terraform AWS provider's database resource sends
``CREATE DATABASE `name`;`` and ``DROP DATABASE `name`;`` (verified in
``internal/service/athena/database.go``), while Trino requires ``SCHEMA`` and
double-quoted identifiers. Rewriting those statements before submit keeps the
stored ``QueryExecution.Query`` identical to the provider's request while
letting the Glue-backed engine execute the resource lifecycle.

awswrangler's table-inspection helpers do the same for utility statements:
``describe_table``/``show_create_table`` submit ``DESCRIBE `t`;`` /
``SHOW CREATE TABLE `t`;`` (awswrangler/athena/_utils.py:659,988), so a
statement-leading DESCRIBE/SHOW CREATE has its backticked object reference
normalized to Trino quoting and its statement terminator dropped.

``repair_table`` submits Hive vocabulary — ``MSCK REPAIR TABLE `t`;``
(awswrangler/athena/_utils.py:581) — which Trino's grammar rejects outright.
Trino's Hive connector documents ``CALL system.sync_partition_metadata
(schema, table, mode[, case_sensitive])`` as the partition-discovery
procedure (trino.io hive connector procedures); its optional
``case_sensitive`` defaults to true, matching Hive's lowercase key-name
convention, so the rewrite emits the three-argument form with ``'ADD'``.

Athena's ``SHOW PARTITIONS [db.]table`` spelling has no Trino statement at
all — the coordinator's SHOW grammar rejects ``PARTITIONS`` outright — so
the statement is rewritten to read the Hive connector's
``<table>$partitions`` system table (trino.io hive connector system
tables), the surface AWS's SHOW PARTITIONS docs themselves name as the
partition-listing equivalent.

Athena's ``CREATE EXTERNAL TABLE`` has no Trino grammar either; the full
clause-by-clause mapping to ``CREATE TABLE … WITH(…)`` — including Hive
type spellings, ``ROW FORMAT``/``STORED AS`` resolution, and the clauses
that raise ``InvalidRequestException`` — lives in ``external_table.py``.

``ALTER TABLE … ADD [IF NOT EXISTS] PARTITION`` is likewise executor-level:
``partition_alter.py`` emits a ``register_partition`` CALL whose
``IF NOT EXISTS`` flag rides the execution record (the procedure's
``ALREADY_EXISTS`` is AWS's no-op).

Only statement-leading rewrites apply; occurrences inside SELECTs, strings,
and comments remain untouched. The mapping is intentionally small and
evidence-gated.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from athena_local.errors import InvalidRequestException
from athena_local.external_table import external_table_trino_ddl
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    balanced_span,
    identifier_name,
    literal_value,
    quoted_identifier,
    split_target,
    split_top_level,
    sql_literal,
    string_end,
)

# The optional IF NOT EXISTS clause is part of the Athena CREATE DATABASE
# grammar and appears in the awscli consumer evidence.  The identifier forms
# cover the provider's backtick spelling and the existing unquoted example.
_DATABASE_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*(?P<action>create|drop)\s+)database\b"
    r"(?P<middle>\s+(?:if\s+not\s+exists\s+)?)"
    r"(?P<identifier>`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*|\"[^\"]+\")"
)

# A bare identifier chain (``db.t``, `` `db`.`t` ``) after a utility keyword;
# anything else — DESCRIBE FORMATTED, a column argument, a second statement —
# fails the anchored match and is left for Trino to reject.
_UTILITY_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*(?:describe|desc|show\s+create\s+(?:table|view))\s+)"
    rf"(?P<target>(?:{IDENTIFIER_PART})(?:\s*\.\s*(?:{IDENTIFIER_PART}))*)"
    r"\s*;?\s*$"
)

# Athena's Hive-vocabulary repair statement takes an optional ``db.``
# qualifier (``MSCK REPAIR TABLE [db.]table``); anything further — a catalog
# level, a partition spec — fails the anchored match for Trino to reject.
_MSCK_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*)msck\s+repair\s+table\s+"
    rf"(?P<target>(?:{IDENTIFIER_PART})(?:\s*\.\s*(?:{IDENTIFIER_PART}))*)"
    r"\s*;?\s*$"
)

# Athena's ``SHOW PARTITIONS [db.]table`` has no Trino statement at all —
# the coordinator's SHOW grammar rejects PARTITIONS outright (probed: every
# FROM/IN spelling fails at the keyword), so the statement reads the Hive
# connector's ``<table>$partitions`` system table, the same surface AWS's
# own SHOW PARTITIONS docs name as the partition-listing equivalent.
_SHOW_PARTITIONS_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*)show\s+partitions\s+"
    rf"(?P<target>(?:{IDENTIFIER_PART})(?:\s*\.\s*(?:{IDENTIFIER_PART}))*)"
    r"\s*;?\s*$"
)

_BACKTICKED_PART = re.compile(r"`([^`]+)`")


def _schema_replacement(match: re.Match[str]) -> str:
    prefix = match.group("prefix")
    action = match.group("action")
    replacement = "SCHEMA" if action.isupper() else "schema"
    identifier = match.group("identifier")
    if identifier.startswith("`"):
        identifier = f'"{identifier[1:-1]}"'
    return f"{prefix}{replacement}{match.group('middle')}{identifier}"


def _utility_replacement(match: re.Match[str]) -> str:
    target = _BACKTICKED_PART.sub(r'"\1"', match.group("target"))
    return f"{match.group('prefix')}{target}"


def _msck_replacement(match: re.Match[str], database: str | None) -> str:
    """The ``CALL system.sync_partition_metadata`` a statement resolves to.

    An unqualified table falls back to the request's Database context; with
    no schema at all the statement passes through for Trino to reject, since
    procedure arguments are varchar literals with no session-schema lookup.
    """
    parts = [identifier_name(p) for p in split_target(match.group("target"))]
    schema, table = (None, None)
    if len(parts) == 1:
        schema, table = database, parts[0]
    if len(parts) == 2:
        schema, table = parts
    if schema is None or table is None:
        return match.group(0)
    return (
        f"{match.group('prefix')}CALL system.sync_partition_metadata("
        f"'{sql_literal(schema)}','{sql_literal(table)}','ADD')"
    )


def _show_partitions_replacement(
    match: re.Match[str], database: str | None
) -> str:
    """The ``SELECT * FROM "<schema>"."<table>$partitions"`` it resolves to.

    An unqualified table falls back to the request's Database context; with
    no schema at all the statement passes through for Trino to reject. The
    emitted read is columnar (one column per partition key) where real
    Athena renders ``key=value`` rows — the shape-vs-content delta AWS's
    own docs accept by naming ``$partitions`` the listing equivalent.
    """
    parts = [identifier_name(p) for p in split_target(match.group("target"))]
    schema, table = (None, None)
    if len(parts) == 1:
        schema, table = database, parts[0]
    if len(parts) == 2:
        schema, table = parts
    if schema is None or table is None:
        return match.group(0)
    # This function's job is emitting a rewritten statement; schema/table
    # names are ``""``-escaped identifier parts from the anchored grammar
    # above, not raw user input.
    return (
        f"{match.group('prefix')}SELECT * FROM "  # nosec B608
        f'"{quoted_identifier(schema)}".'
        f'"{quoted_identifier(table)}$partitions"'
    )


def to_trino_dialect(query: str, database: str | None = None) -> str:
    """Map Athena-only statements to Trino's executable vocabulary.

    ``create database if not exists newdb`` and the provider's backtick form
    become ``create schema`` with a Trino-compatible identifier, a
    statement-leading ``drop database`` follows the same mapping,
    ``DESCRIBE``/``SHOW CREATE TABLE|VIEW`` get double-quoted identifiers
    without the statement terminator, ``MSCK REPAIR TABLE`` becomes a
    ``CALL system.sync_partition_metadata(…, 'ADD')`` whose schema comes
    from the statement's qualified name or ``database`` — the request's
    ``QueryExecutionContext.Database`` — and ``SHOW PARTITIONS`` reads the
    ``<table>$partitions`` system table under the same schema rule, and
    ``CREATE EXTERNAL TABLE … LOCATION`` becomes a ``CREATE TABLE … WITH
    (format, external_location[, partitioned_by])`` (see
    ``external_table.py``). All other statements pass through unchanged.
    """
    if _DATABASE_STATEMENT.match(query) is not None:
        mapped = _DATABASE_STATEMENT.sub(_schema_replacement, query, count=1)
        return re.sub(r";\s*$", "", mapped, count=1)
    utility = _UTILITY_STATEMENT.match(query)
    if utility is not None:
        return _utility_replacement(utility)
    external = external_table_trino_ddl(query, database)
    if external is not None:
        return external
    show_partitions = _SHOW_PARTITIONS_STATEMENT.match(query)
    if show_partitions is not None:
        return _show_partitions_replacement(show_partitions, database)
    msck = _MSCK_STATEMENT.match(query)
    if msck is None:
        return query
    return _msck_replacement(msck, database)


# UNLOAD is Athena vocabulary Trino's grammar lacks outright (measured
# against the coordinator): ``UNLOAD (query) TO 's3://…' WITH (props)`` maps
# to a CTAS writing the same location through a generated temp table, whose
# Glue entry the executor deletes on completion — real UNLOAD registers no
# table. Trino's hive connector takes the write codec as the
# ``hive.compression_codec`` session property, not a table property
# (probed ``system.metadata.table_properties``), so ``compression`` travels
# on the request's session headers instead of the emitted SQL.
_UNLOAD_HEAD_RE = re.compile(r"(?i)^\s*unload\s*\(")
_UNLOAD_TO_RE = re.compile(r"(?i)\s*to\s*'")
_UNLOAD_WITH_RE = re.compile(r"(?i)\s*with\s*\(")
_UNLOAD_TAIL_RE = re.compile(r"\s*;?\s*")

_UNLOAD_SUPPORTED_PROPS = frozenset(
    {"format", "compression", "field_delimiter", "partitioned_by"}
)
# Athena's lowercase compression names → Trino HiveCompressionCodec values;
# 'zlib' has no Trino codec and is rejected rather than silently mapped.
_UNLOAD_COMPRESSION_CODECS = {
    "none": "NONE",
    "snappy": "SNAPPY",
    "lz4": "LZ4",
    "zstd": "ZSTD",
    "gzip": "GZIP",
}


@dataclass(frozen=True)
class UnloadSubmission:
    """The Trino CTAS an UNLOAD statement resolves to, plus its cleanup.

    ``cleanup_table`` names the ``(schema, table)`` Glue entry the emitted
    CTAS registers — the executor deletes it when the statement ends so the
    catalog shows no residue of a statement real Athena keeps table-less.
    """

    sql: str
    session_properties: dict[str, str]
    cleanup_table: tuple[str, str]


@dataclass(frozen=True)
class _UnloadParts:
    """The parsed pieces of ``UNLOAD (inner) TO 'loc' WITH (props)``."""

    inner: str
    location: str
    properties: dict[str, str]


def unload_trino_submission(
    query: str, database: str | None
) -> UnloadSubmission | None:
    """Map an UNLOAD statement to a Trino CTAS at its ``TO`` location.

    Returns None — leaving the statement for Trino to reject — when the
    text is not UNLOAD-shaped, is unbalanced, has no ``TO`` clause, or has
    no ``database`` context to host the temp table (the stack's Glue has
    no ``default`` database). Raises ``InvalidRequestException`` for
    properties the rewrite cannot honor — an unknown key, a ``compression``
    value with no Trino codec, or a missing ``format`` — since real Athena
    also rejects a malformed UNLOAD at submit.
    """
    parts = _parse_unload(query)
    if parts is None or database is None:
        return None
    unsupported = sorted(set(parts.properties) - _UNLOAD_SUPPORTED_PROPS)
    if unsupported:
        raise InvalidRequestException(
            f"UNLOAD property {unsupported[0]!r} is not supported; "
            f"expected one of {sorted(_UNLOAD_SUPPORTED_PROPS)}"
        )
    file_format = literal_value(parts.properties.get("format"))
    if file_format is None:
        raise InvalidRequestException(
            "UNLOAD requires a 'format' property in its WITH clause; "
            "expected one of PARQUET, ORC, AVRO, JSON, TEXTFILE"
        )
    session_properties = _unload_session_properties(parts.properties)
    temp_table = f"athena_unload_{uuid.uuid4().hex[:16]}"
    sql = (
        f'CREATE TABLE "{quoted_identifier(database)}"."{temp_table}" '
        f"WITH ({', '.join(_unload_table_properties(parts, file_format))}) "
        f"AS {parts.inner}"
    )
    return UnloadSubmission(
        sql=sql,
        session_properties=session_properties,
        cleanup_table=(database, temp_table),
    )


def _unload_table_properties(
    parts: _UnloadParts, file_format: str
) -> list[str]:
    """The CTAS ``WITH`` clause entries, in deterministic order."""
    properties = [
        f"format='{sql_literal(file_format.upper())}'",
        f"external_location='{sql_literal(parts.location)}'",
    ]
    # partitioned_by is the same ARRAY[...] expression in both dialects;
    # field_delimiter maps to the TEXTFILE separator property (probed
    # property names) — a no-op for columnar formats, like Athena.
    partitioned_by = parts.properties.get("partitioned_by")
    if partitioned_by is not None:
        properties.append(f"partitioned_by={partitioned_by}")
    field_delimiter = parts.properties.get("field_delimiter")
    if field_delimiter is not None:
        properties.append(f"textfile_field_separator={field_delimiter}")
    return properties


def _unload_session_properties(
    properties: dict[str, str],
) -> dict[str, str]:
    """WITH-clause values that travel as session properties, not DDL."""
    compression = literal_value(properties.get("compression"))
    if compression is None:
        return {}
    codec = _UNLOAD_COMPRESSION_CODECS.get(compression.lower())
    if codec is None:
        raise InvalidRequestException(
            f"UNLOAD compression {compression!r} has no Trino write codec; "
            f"expected one of {sorted(_UNLOAD_COMPRESSION_CODECS)}"
        )
    return {"hive.compression_codec": codec}


def _parse_unload(query: str) -> _UnloadParts | None:
    """The ``(inner, TO, WITH)`` pieces of an UNLOAD, or None if not one."""
    head = _UNLOAD_HEAD_RE.match(query)
    if head is None:
        return None
    inner_start = head.end() - 1
    inner_end = balanced_span(query, inner_start)
    if inner_end is None:
        return None
    inner = query[inner_start + 1 : inner_end - 1].strip()
    to_match = _UNLOAD_TO_RE.match(query, inner_end)
    if to_match is None:
        return None
    location_end = string_end(query, to_match.end() - 1)
    if location_end is None:
        return None
    location = query[to_match.end() : location_end - 1].replace("''", "'")
    properties, tail = _parse_unload_with(query, location_end)
    if properties is None or _UNLOAD_TAIL_RE.fullmatch(tail) is None:
        return None
    return _UnloadParts(inner=inner, location=location, properties=properties)


def _parse_unload_with(
    query: str, start: int
) -> tuple[dict[str, str] | None, str]:
    """``WITH (k=v, …)`` at ``start`` → (properties, remaining tail)."""
    with_match = _UNLOAD_WITH_RE.match(query, start)
    if with_match is None:
        return {}, query[start:]
    props_start = with_match.end() - 1
    props_end = balanced_span(query, props_start)
    if props_end is None:
        return None, ""
    return (
        _with_properties(query[props_start + 1 : props_end - 1]),
        query[props_end:],
    )


def _with_properties(text: str) -> dict[str, str] | None:
    """``k = v`` pairs split on top-level commas; keys fold to lowercase."""
    properties: dict[str, str] = {}
    for pair in split_top_level(text):
        key, separator, value = pair.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if not separator or not re.fullmatch(r"[a-z_][a-z0-9_]*", key):
            return None
        if not value:
            return None
        properties[key] = value
    return properties
