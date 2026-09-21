"""Statement classification (statement_classification.py) tests.

The mapping mirrors the semantics real Athena engine v3 reports and its
consumers rely on: ``SELECT`` is DML, ``CREATE TABLE ... AS`` is DDL (a
FAILED CTAS on engine v3 still reported StatementType ``DDL`` with
``SubstatementType`` ``CREATE_TABLE_AS_SELECT``, and awswrangler's
``get_query_results`` keys the manifest path off
``statement_type == "DDL" and Query.startswith("CREATE TABLE")`` —
``awswrangler/athena/_read.py:912-934``). ``SubstatementType`` is a
free-form string in the service model, so the UPPER_SNAKE values below are
emulator-owned, matching the names in the Athena release notes (SELECT,
INSERT, UNLOAD, CREATE_TABLE, CREATE_TABLE_AS_SELECT).
"""

from __future__ import annotations

import pytest
from athena_local.statement_classification import (
    StatementClassification,
    classify_statement,
)


def _identifier(case: tuple[str, str, str | None]) -> str:
    """Short pytest node id from the query's leading keyword."""
    stripped = case[0].strip().split()
    return stripped[0].upper() if stripped else "empty"


CLASSIFICATION_CASES = [
    # (query, statement_type, substatement_type)
    ("SELECT 1", "DML", "SELECT"),
    ("select 1", "DML", "SELECT"),
    ("  SELECT 1", "DML", "SELECT"),
    ("\n\tSELECT 1", "DML", "SELECT"),
    ("-- comment\nSELECT 1", "DML", "SELECT"),
    ("/* block comment */\nSELECT 1", "DML", "SELECT"),
    ("-- 'quoted text' inside a comment\nSELECT 1", "DML", "SELECT"),
    ("SELECT '-- not a comment' AS text_value", "DML", "SELECT"),
    ("SELECT '/* not a comment */' AS text_value", "DML", "SELECT"),
    ("SELECT 'it''s -- not a comment' AS text_value", "DML", "SELECT"),
    (
        "/* unterminated comment\nSELECT 1",
        "UTILITY",
        None,
    ),
    (
        "WITH ranked AS (SELECT 1 AS n) SELECT n FROM ranked",
        "DML",
        "SELECT",
    ),
    (
        "CREATE TABLE db.table "
        "WITH (external_location = 's3://bucket/path', format = 'PARQUET') "
        "AS SELECT 1 AS n",
        "DDL",
        "CREATE_TABLE_AS_SELECT",
    ),
    (
        "CREATE TABLE db.table WITH (format = 'PARQUET') "
        "AS SELECT 1 AS n WITH NO DATA",
        "DDL",
        "CREATE_TABLE_AS_SELECT",
    ),
    ("CREATE TABLE t (id INTEGER)", "DDL", "CREATE_TABLE"),
    ("CREATE DATABASE analytics", "DDL", "CREATE_DATABASE"),
    ("drop table t", "DDL", "DROP_TABLE"),
    ("ALTER TABLE t ADD COLUMN c INTEGER", "DDL", "ALTER_TABLE"),
    ("GRANT SELECT ON t TO alice", "DDL", "GRANT"),
    ("INSERT INTO t SELECT 1 AS n", "DML", "INSERT"),
    (
        "UNLOAD (SELECT 1 AS n) TO 's3://bucket/path' "
        "WITH (format = 'PARQUET')",
        "DML",
        "UNLOAD",
    ),
    ("DELETE FROM t WHERE id = 1", "DML", "DELETE"),
    ("UPDATE t SET value = 1 WHERE id = 1", "DML", "UPDATE"),
    ("SHOW CREATE TABLE t", "UTILITY", "SHOW_CREATE_TABLE"),
    ("SHOW TABLES FROM analytics", "UTILITY", "SHOW_TABLES"),
    ("DESCRIBE t", "UTILITY", "DESCRIBE"),
    ("desc t", "UTILITY", "DESCRIBE"),
    ("EXPLAIN SELECT 1", "UTILITY", "EXPLAIN_SELECT"),
    ("USE analytics", "UTILITY", "USE_ANALYTICS"),
    ("ANALYZE TABLE t", "UTILITY", "ANALYZE_TABLE"),
    ("SET SESSION query_max_run_time = '1h'", "UTILITY", "SET_SESSION"),
    ("CALL system.runtime.kill_query('id')", "UTILITY", "CALL_SYSTEM"),
    ("FOOBAR some statement", "UTILITY", None),
    ("", "UTILITY", None),
    ("   ", "UTILITY", None),
]


@pytest.mark.parametrize(
    "query,statement_type,substatement_type",
    CLASSIFICATION_CASES,
    ids=[_identifier(case) for case in CLASSIFICATION_CASES],
)
def test_classify_statement(
    query: str,
    statement_type: str,
    substatement_type: str | None,
) -> None:
    classification = classify_statement(query)

    assert classification == StatementClassification(
        statement_type=statement_type,
        substatement_type=substatement_type,
    )
