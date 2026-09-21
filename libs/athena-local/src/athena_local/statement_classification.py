"""Pure-text statement classification into Athena's wire type fields.

Real Athena classifies a query at submit time — a FAILED statement still
reports ``StatementType``/``SubstatementType`` — and its consumers key
artifact handling off these two fields: awswrangler treats ``CREATE TABLE
... AS`` as DDL and ``UNLOAD`` as DML (``awswrangler/athena/_read.py:912-934``),
RAthena deletes the manifest for DDL results, and ``SHOW TABLES`` is
documented as UTILITY "not DDL". ``SubstatementType`` is a free-form string
in the service model (service-2.json ``QueryExecution``), so the UPPER_SNAKE
values below are emulator-owned, matching the names the Athena release notes
publish (SELECT, INSERT, UNLOAD, CREATE_TABLE, CREATE_TABLE_AS_SELECT).

Classification is a pure function of the query text and never alters the SQL
sent to Trino; it only reads a comment-stripped copy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

DDL = "DDL"
DML = "DML"
UTILITY = "UTILITY"

# StatementType per the model enum (service-2.json StatementType shape).
StatementType = Literal["DDL", "DML", "UTILITY"]

DML_STATEMENTS = frozenset(
    {
        "SELECT",
        "WITH",
        "VALUES",
        "TABLE",
        "INSERT",
        "UNLOAD",
        "DELETE",
        "UPDATE",
        "MERGE",
    }
)
DDL_STATEMENTS = frozenset({"CREATE", "DROP", "ALTER", "GRANT", "REVOKE"})
UTILITY_STATEMENTS = frozenset(
    {
        "SHOW",
        "DESCRIBE",
        "DESC",
        "EXPLAIN",
        "USE",
        "ANALYZE",
        "SET",
        "RESET",
        "CALL",
        "PREPARE",
        "EXECUTE",
        "DEALLOCATE",
    }
)


@dataclass(frozen=True)
class StatementClassification:
    """The two wire fields describing what a query statement is."""

    statement_type: StatementType
    substatement_type: str | None


def classify_statement(query: str) -> StatementClassification:
    """Classify a SQL statement from its leading keywords, case-insensitively."""
    tokens = _leading_tokens(query)
    first_token = tokens[0] if tokens else None
    if first_token in DML_STATEMENTS:
        return StatementClassification(
            DML, _dml_substatement(first_token, tokens)
        )
    if first_token in DDL_STATEMENTS:
        return StatementClassification(
            DDL, _ddl_substatement(first_token, tokens)
        )
    if first_token in UTILITY_STATEMENTS:
        return StatementClassification(
            UTILITY, _utility_substatement(first_token, tokens)
        )
    # Unknown statements fall into UTILITY, the model's "other than DDL and
    # DML" bucket; there is nothing finer to report as a sub-statement.
    return StatementClassification(UTILITY, None)


def _leading_tokens(query: str) -> list[str]:
    return _strip_comments(query).upper().split()


# Alternation order is load-bearing: a string literal is matched whole
# (including its ``''`` escapes) before any comment marker inside it, so
# ``'-- x'`` or ``'/* x */'`` text cannot skew the leading keyword. An
# unterminated ``/*`` swallows to end of input, matching the old scanner.
_COMMENT_ISOLATING_RE = re.compile(
    r"'(?:[^']|'')*'|--[^\n]*|/\*.*?\*/|/\*.*|.",
    re.DOTALL,
)


def _strip_comments(sql: str) -> str:
    """Drop ``--`` and ``/* */`` comments outside string literals.

    Only the classification copy is stripped; the original query is what
    reaches Trino.
    """
    kept: list[str] = []
    for match in _COMMENT_ISOLATING_RE.finditer(sql):
        token = match.group(0)
        if not token.startswith(("--", "/*")):
            kept.append(token)
    return "".join(kept)


def _dml_substatement(first_token: str, tokens: list[str]) -> str:
    # WITH / TABLE are SELECT sugar; the sub-statement that ran is a SELECT.
    if first_token in {"WITH", "TABLE"}:
        return "SELECT"
    return first_token


def _ddl_substatement(first_token: str, tokens: list[str]) -> str:
    if first_token == "CREATE" and len(tokens) > 1 and tokens[1] == "TABLE":
        if "AS" in tokens[2:]:
            return "CREATE_TABLE_AS_SELECT"
        return "CREATE_TABLE"
    if first_token in {"CREATE", "DROP", "ALTER"} and len(tokens) > 1:
        return f"{first_token}_{tokens[1]}"
    return first_token


def _utility_substatement(first_token: str, tokens: list[str]) -> str:
    if first_token in {"DESCRIBE", "DESC"}:
        return "DESCRIBE"
    if first_token == "SHOW" and len(tokens) > 1:
        if tokens[1] == "CREATE" and len(tokens) > 2:
            return f"SHOW_{tokens[1]}_{tokens[2]}"
        return f"SHOW_{tokens[1]}"
    if len(tokens) > 1:
        return f"{first_token}_{_word_prefix(tokens[1])}"
    return first_token


def _word_prefix(token: str) -> str:
    """Leading [A-Z0-9_] word of a token (quotes/parens/dots are noise)."""
    match = re.match(r"[A-Z0-9_]+", token)
    return match.group(0) if match else ""
