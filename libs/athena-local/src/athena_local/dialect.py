"""Athena-to-Trino statement dialect map.

Real Athena parses a slightly wider SQL vocabulary than the Trino 483 engine
underneath this emulator. The Terraform AWS provider's database resource sends
``CREATE DATABASE `name`;`` and ``DROP DATABASE `name`;`` (verified in
``internal/service/athena/database.go``), while Trino requires ``SCHEMA`` and
double-quoted identifiers. Rewriting those statements before submit keeps the
stored ``QueryExecution.Query`` identical to the provider's request while
letting the Glue-backed engine execute the resource lifecycle.

Only a statement-leading CREATE/DROP DATABASE is rewritten; occurrences inside
SELECTs, strings, and comments remain untouched. The mapping is intentionally
small and evidence-gated.
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


def _schema_replacement(match: re.Match[str]) -> str:
    prefix = match.group("prefix")
    action = match.group("action")
    replacement = "SCHEMA" if action.isupper() else "schema"
    identifier = match.group("identifier")
    if identifier.startswith("`"):
        identifier = f'"{identifier[1:-1]}"'
    return f"{prefix}{replacement}{match.group('middle')}{identifier}"


def to_trino_dialect(query: str) -> str:
    """Map Athena database lifecycle statements to Trino's schema vocabulary.

    ``create database if not exists newdb`` and the provider's backtick form
    become ``create schema`` with a Trino-compatible identifier.  A
    statement-leading ``drop database`` follows the same mapping; all other
    statements pass through unchanged.
    """
    if _DATABASE_STATEMENT.match(query) is None:
        return query
    mapped = _DATABASE_STATEMENT.sub(_schema_replacement, query, count=1)
    return re.sub(r";\s*$", "", mapped, count=1)
