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

Only statement-leading rewrites apply; occurrences inside SELECTs, strings,
and comments remain untouched. The mapping is intentionally small and
evidence-gated.
"""

from __future__ import annotations

import re

# The optional IF NOT EXISTS clause is part of the Athena CREATE DATABASE
# grammar and appears in the awscli consumer evidence.  The identifier forms
# cover the provider's backtick spelling and the existing unquoted example.
_DATABASE_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*(?P<action>create|drop)\s+)database\b"
    r"(?P<middle>\s+(?:if\s+not\s+exists\s+)?)"
    r"(?P<identifier>`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*|\"[^\"]+\")"
)

_IDENTIFIER_PART = r"`[^`]+`|\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_$]*"

# A bare identifier chain (``db.t``, `` `db`.`t` ``) after a utility keyword;
# anything else — DESCRIBE FORMATTED, a column argument, a second statement —
# fails the anchored match and is left for Trino to reject.
_UTILITY_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*(?:describe|desc|show\s+create\s+(?:table|view))\s+)"
    rf"(?P<target>(?:{_IDENTIFIER_PART})(?:\s*\.\s*(?:{_IDENTIFIER_PART}))*)"
    r"\s*;?\s*$"
)

# Athena's Hive-vocabulary repair statement takes an optional ``db.``
# qualifier (``MSCK REPAIR TABLE [db.]table``); anything further — a catalog
# level, a partition spec — fails the anchored match for Trino to reject.
_MSCK_STATEMENT = re.compile(
    r"(?i)^(?P<prefix>\s*)msck\s+repair\s+table\s+"
    rf"(?P<target>(?:{_IDENTIFIER_PART})(?:\s*\.\s*(?:{_IDENTIFIER_PART}))*)"
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


def _split_target(target: str) -> list[str]:
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


def _msck_identifier(part: str) -> str:
    """Unquote a chain segment; bare identifiers fold per Athena's rule."""
    part = part.strip()
    if len(part) >= 2 and part[0] == part[-1] and part[0] in '`"':
        return part[1:-1]
    return part.lower()


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _msck_replacement(match: re.Match[str], database: str | None) -> str:
    """The ``CALL system.sync_partition_metadata`` a statement resolves to.

    An unqualified table falls back to the request's Database context; with
    no schema at all the statement passes through for Trino to reject, since
    procedure arguments are varchar literals with no session-schema lookup.
    """
    parts = [_msck_identifier(p) for p in _split_target(match.group("target"))]
    schema, table = (None, None)
    if len(parts) == 1:
        schema, table = database, parts[0]
    if len(parts) == 2:
        schema, table = parts
    if schema is None or table is None:
        return match.group(0)
    return (
        f"{match.group('prefix')}CALL system.sync_partition_metadata("
        f"'{_sql_literal(schema)}','{_sql_literal(table)}','ADD')"
    )


def to_trino_dialect(query: str, database: str | None = None) -> str:
    """Map Athena-only statements to Trino's executable vocabulary.

    ``create database if not exists newdb`` and the provider's backtick form
    become ``create schema`` with a Trino-compatible identifier, a
    statement-leading ``drop database`` follows the same mapping,
    ``DESCRIBE``/``SHOW CREATE TABLE|VIEW`` get double-quoted identifiers
    without the statement terminator, and ``MSCK REPAIR TABLE`` becomes a
    ``CALL system.sync_partition_metadata(…, 'ADD')`` whose schema comes
    from the statement's qualified name or ``database`` — the request's
    ``QueryExecutionContext.Database``. All other statements pass through
    unchanged.
    """
    if _DATABASE_STATEMENT.match(query) is not None:
        mapped = _DATABASE_STATEMENT.sub(_schema_replacement, query, count=1)
        return re.sub(r";\s*$", "", mapped, count=1)
    utility = _UTILITY_STATEMENT.match(query)
    if utility is not None:
        return _utility_replacement(utility)
    msck = _MSCK_STATEMENT.match(query)
    if msck is None:
        return query
    return _msck_replacement(msck, database)
