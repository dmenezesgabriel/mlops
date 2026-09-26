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


def to_trino_dialect(query: str) -> str:
    """Map Athena-only statements to Trino's executable vocabulary.

    ``create database if not exists newdb`` and the provider's backtick form
    become ``create schema`` with a Trino-compatible identifier, a
    statement-leading ``drop database`` follows the same mapping, and
    ``DESCRIBE``/``SHOW CREATE TABLE|VIEW`` get double-quoted identifiers
    without the statement terminator. All other statements pass through
    unchanged.
    """
    if _DATABASE_STATEMENT.match(query) is not None:
        mapped = _DATABASE_STATEMENT.sub(_schema_replacement, query, count=1)
        return re.sub(r";\s*$", "", mapped, count=1)
    utility = _UTILITY_STATEMENT.match(query)
    if utility is None:
        return query
    return _utility_replacement(utility)
