"""Unit tests for the Athena→Trino dialect map (``dialect.py``).

The CLI ``start-query-execution`` example runs
``create database if not exists newdb`` (valid Athena DDL — Athena's SQL
reference supports CREATE DATABASE), but Trino 483 rejects it (its Hive
connector vocabulary is ``CREATE SCHEMA``). The provider's exact lifecycle
spelling adds backtick identifiers and a terminal semicolon, which Trino also
rejects. Rewrites apply only to submitted statements; classification and
stored query text keep the original Athena SQL.
"""

from __future__ import annotations

import re

import pytest
from athena_local.dialect import (
    UnloadSubmission,
    to_trino_dialect,
    unload_trino_submission,
)
from athena_local.errors import InvalidRequestException

# The emitted CTAS always targets a generated temp table name; the regex
# pulls the (schema, table) pair for assertions without pinning the uuid.
_EMITTED_CTAS_RE = re.compile(
    r'^CREATE TABLE "(?P<schema>[^"]+)"\.'
    r'"(?P<table>athena_unload_[0-9a-f]+)"'
)


def test_create_database_becomes_create_schema() -> None:
    assert (
        to_trino_dialect("create database if not exists newdb")
        == "create schema if not exists newdb"
    )


def test_provider_database_statements_use_trino_identifiers() -> None:
    assert to_trino_dialect("create database `analytics`;") == (
        'create schema "analytics"'
    )
    assert to_trino_dialect("drop database `analytics`;") == (
        'drop schema "analytics"'
    )


def test_uppercase_and_leading_whitespace_are_preserved() -> None:
    assert (
        to_trino_dialect("  CREATE DATABASE analytics")
        == "  CREATE SCHEMA analytics"
    )


@pytest.mark.parametrize(
    "query",
    [
        "select 1",
        "create table t (a integer)",
        "INSERT INTO x SELECT 'create database' FROM y",
    ],
)
def test_non_matching_statements_pass_through(query: str) -> None:
    assert to_trino_dialect(query) == query


@pytest.mark.parametrize(
    "query,expected",
    [
        ("DESCRIBE `sales`;", 'DESCRIBE "sales"'),
        ("desc `sales`;", 'desc "sales"'),
        ("DESCRIBE `analytics`.`sales`;", 'DESCRIBE "analytics"."sales"'),
        ("SHOW CREATE TABLE `sales`;", 'SHOW CREATE TABLE "sales"'),
        ("SHOW CREATE VIEW `v`;", 'SHOW CREATE VIEW "v"'),
        ("  describe `sales` ;", '  describe "sales"'),
        ("DESCRIBE sales;", "DESCRIBE sales"),
        ("DESCRIBE analytics.sales", "DESCRIBE analytics.sales"),
    ],
)
def test_utility_statements_use_trino_identifiers(
    query: str, expected: str
) -> None:
    assert to_trino_dialect(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        "DESCRIBE FORMATTED `sales`",
        "DESCRIBE `sales` extra_column",
        "SHOW CREATE TABLE `sales` AS SELECT 1",
        "SELECT 'describe `x`' FROM t",
    ],
)
def test_utility_statements_with_extra_syntax_pass_through(
    query: str,
) -> None:
    assert to_trino_dialect(query) == query


@pytest.mark.parametrize(
    "query,database,expected",
    [
        (
            "MSCK REPAIR TABLE `sales`;",
            "analytics",
            "CALL system.sync_partition_metadata('analytics','sales','ADD')",
        ),
        (
            "MSCK REPAIR TABLE `db`.`sales`",
            None,
            "CALL system.sync_partition_metadata('db','sales','ADD')",
        ),
        # A qualified name wins over the request's database context.
        (
            "msck repair table db.sales;",
            "other",
            "CALL system.sync_partition_metadata('db','sales','ADD')",
        ),
        # Athena folds unquoted identifiers; quoted names keep their case.
        (
            "MSCK REPAIR TABLE DB.SALES",
            None,
            "CALL system.sync_partition_metadata('db','sales','ADD')",
        ),
        (
            'MSCK REPAIR TABLE "Db"."Sales"',
            None,
            "CALL system.sync_partition_metadata('Db','Sales','ADD')",
        ),
        # SQL literals escape single quotes.
        (
            "MSCK REPAIR TABLE `we'ird`;",
            "db",
            "CALL system.sync_partition_metadata('db','we''ird','ADD')",
        ),
        (
            "  MSCK REPAIR TABLE `sales`",
            "analytics",
            "  CALL system.sync_partition_metadata('analytics','sales','ADD')",
        ),
    ],
)
def test_msck_repair_table_maps_to_sync_partition_metadata(
    query: str, database: str | None, expected: str
) -> None:
    assert to_trino_dialect(query, database) == expected


@pytest.mark.parametrize(
    "query",
    [
        # No qualified schema and no request context — left for Trino to
        # reject (procedure arguments are literals, no session schema).
        "MSCK REPAIR TABLE `sales`",
        "MSCK REPAIR TABLE catalog.db.sales",
        "MSCK REPAIR TABLE",
        "MSCK REPAIR `sales`",
        "MSCK REPAIR TABLE `sales` PARTITION ('x')",
        "SELECT 'MSCK REPAIR TABLE x' FROM t",
    ],
)
def test_msck_statements_that_cannot_resolve_a_schema_pass_through(
    query: str,
) -> None:
    assert to_trino_dialect(query) == query


@pytest.mark.parametrize(
    "query,database,expected",
    [
        (
            "SHOW PARTITIONS `sales`;",
            "analytics",
            'SELECT * FROM "analytics"."sales$partitions"',
        ),
        (
            "SHOW PARTITIONS sales",
            "analytics",
            'SELECT * FROM "analytics"."sales$partitions"',
        ),
        # A qualified name wins over the request's database context.
        (
            "SHOW PARTITIONS `db`.`sales`",
            "other",
            'SELECT * FROM "db"."sales$partitions"',
        ),
        (
            "show partitions db.sales;",
            None,
            'SELECT * FROM "db"."sales$partitions"',
        ),
        # Athena folds unquoted identifiers; quoted names keep their case.
        (
            "SHOW PARTITIONS DB.SALES",
            None,
            'SELECT * FROM "db"."sales$partitions"',
        ),
        (
            'SHOW PARTITIONS "Db"."Sales"',
            None,
            'SELECT * FROM "Db"."Sales$partitions"',
        ),
        (
            "  SHOW PARTITIONS `sales`",
            "analytics",
            '  SELECT * FROM "analytics"."sales$partitions"',
        ),
        # Inner double quotes escape for the quoted Trino identifier.
        (
            'SHOW PARTITIONS "we""ird"',
            "db",
            'SELECT * FROM "db"."we""ird$partitions"',
        ),
    ],
)
def test_show_partitions_maps_to_partitions_virtual_table(
    query: str, database: str | None, expected: str
) -> None:
    assert to_trino_dialect(query, database) == expected


@pytest.mark.parametrize(
    "query,database",
    [
        # No qualified schema and no request context — left for Trino to
        # reject, same posture as an unresolvable MSCK schema.
        ("SHOW PARTITIONS `sales`", None),
        ("SHOW PARTITIONS catalog.db.sales", "db"),
        ("SHOW PARTITIONS", "db"),
        # Hive's PARTITION() filter and Trino's FROM spelling are not the
        # Athena grammar — AWS rejects them the same way Trino does.
        ("SHOW PARTITIONS sales PARTITION (region='US')", "db"),
        ("SHOW PARTITIONS FROM sales", "db"),
        ("SHOW PARTITIONS sales; SELECT 1", "db"),
        ("SELECT 'SHOW PARTITIONS x' FROM t", "db"),
    ],
)
def test_show_partitions_unmapped_statements_pass_through(
    query: str, database: str | None
) -> None:
    assert to_trino_dialect(query, database) == query


def _emitted_table(submission: UnloadSubmission) -> tuple[str, str]:
    """The ``(schema, table)`` an emitted UNLOAD-CTAS registers then drops."""
    match = _EMITTED_CTAS_RE.match(submission.sql)
    assert match is not None, f"not an emitted CTAS: {submission.sql}"
    return match.group("schema"), match.group("table")


def test_unload_rewrites_to_ctas_at_the_to_path() -> None:
    # awswrangler's exact wire spelling (athena/_read.py _unload): lowercase
    # keyword inside WITH, the format property first.
    submission = unload_trino_submission(
        "UNLOAD (SELECT * FROM sales) TO 's3://bucket/unload/' "
        "WITH (  format='PARQUET')",
        "analytics",
    )

    assert submission is not None
    assert submission.sql == (
        'CREATE TABLE "analytics"."'
        f"{_emitted_table(submission)[1]}\" WITH (format='PARQUET', "
        "external_location='s3://bucket/unload/') AS SELECT * FROM sales"
    )
    assert submission.cleanup_table == _emitted_table(submission)
    assert submission.session_properties == {}


def test_unload_maps_every_with_property() -> None:
    submission = unload_trino_submission(
        "UNLOAD (SELECT * FROM sales) TO 's3://bucket/u/' "
        "WITH (format='TEXTFILE', field_delimiter='\\t', "
        "partitioned_by=ARRAY['region', 'amount'], compression='snappy')",
        "db",
    )

    assert submission is not None
    assert (
        "WITH (format='TEXTFILE', external_location='s3://bucket/u/', "
        "partitioned_by=ARRAY['region', 'amount'], "
        "textfile_field_separator='\\t') AS SELECT * FROM sales"
    ) in submission.sql
    # Trino's hive connector takes the write codec as a session property,
    # not a table property (probed: system.metadata.table_properties).
    assert submission.session_properties == {
        "hive.compression_codec": "SNAPPY"
    }


def test_unload_to_literal_keeps_escaped_quotes() -> None:
    submission = unload_trino_submission(
        "UNLOAD (SELECT 1) TO 's3://b/we''ird/' WITH (format='JSON')", "d"
    )

    assert submission is not None
    assert "external_location='s3://b/we''ird/'" in submission.sql


def test_unload_inner_query_keeps_nested_parens_and_strings() -> None:
    inner = "SELECT concat(')', '(') FROM t WHERE a IN (1, 2)"
    submission = unload_trino_submission(
        f"unload ({inner}) to 's3://b/o/' with (format='orc');", "d"
    )

    assert submission is not None
    assert submission.sql.endswith(f"AS {inner}")


def test_unload_generates_distinct_temp_table_names() -> None:
    query = "UNLOAD (SELECT 1) TO 's3://b/o/' WITH (format='PARQUET')"
    first = unload_trino_submission(query, "d")
    second = unload_trino_submission(query, "d")

    assert first is not None and second is not None
    assert _emitted_table(first)[1] != _emitted_table(second)[1]


@pytest.mark.parametrize(
    "query,database",
    [
        # No schema for the temp table — the statement passes through for
        # Trino to reject, same as an unresolvable MSCK schema.
        ("UNLOAD (SELECT 1) TO 's3://b/o/' WITH (format='PARQUET')", None),
        ("UNLOAD SELECT * FROM t", "d"),  # missing the parenthesized query
        ("UNLOAD (SELECT * FROM t", "d"),  # unbalanced
        ("UNLOAD (SELECT * FROM t) WHERE x = 1", "d"),  # no TO clause
        (
            "UNLOAD (SELECT * FROM t) TO 's3://b/o/' WITH (format='PARQUET') ;"
            " SELECT 1",
            "d",
        ),  # a second statement
        ("SELECT 'unload (x) to ''y'''", "d"),  # keyword inside a literal
    ],
)
def test_unload_unmapped_statements_pass_through(
    query: str, database: str | None
) -> None:
    assert unload_trino_submission(query, database) is None


@pytest.mark.parametrize(
    "query,offender",
    [
        (
            "UNLOAD (SELECT 1) TO 's3://b/' WITH (compression='zlib', "
            "format='ORC')",
            "zlib",
        ),
        (
            "UNLOAD (SELECT 1) TO 's3://b/' WITH (compression_level=3, "
            "format='PARQUET')",
            "compression_level",
        ),
        (
            "UNLOAD (SELECT 1) TO 's3://b/' WITH (bogus_property='x', "
            "format='PARQUET')",
            "bogus_property",
        ),
        # format is the only property real Athena requires; a WITH clause
        # without it must not silently become Trino's default format.
        (
            "UNLOAD (SELECT 1) TO 's3://b/' WITH (compression='snappy')",
            "format",
        ),
        ("UNLOAD (SELECT 1) TO 's3://b/'", "format"),
    ],
)
def test_unload_unsupported_properties_raise_a_shaped_400(
    query: str, offender: str
) -> None:
    with pytest.raises(InvalidRequestException, match=offender):
        unload_trino_submission(query, "db")
