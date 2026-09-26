"""Unit tests for ``partition_alter.py`` — Athena ``ALTER TABLE … ADD
PARTITION`` → Trino ``system.register_partition``.

Real Athena registers partitions with
``ALTER TABLE t ADD [IF NOT EXISTS] PARTITION (col='v' [, …]) [LOCATION
's3://…']`` (AWS docs ``alter-table-add-partition.html``); Trino 483's
grammar has no ``ADD PARTITION`` form at all, so the statement is rewritten
to the Hive connector's ``CALL system.register_partition(schema, table,
partition_columns, partition_values[, location])`` — the 5-argument
signature probed against the coordinator, whose ``LOCATION`` is optional
(procedure defaults it to the table's hive-layout partition path).
"""

from __future__ import annotations

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.partition_alter import (
    AddPartitionCall,
    add_partition_trino_call,
)


def test_add_partition_maps_to_register_partition_call() -> None:
    call = add_partition_trino_call(
        "ALTER TABLE sales ADD PARTITION (region='AP') "
        "LOCATION 's3://b/sales/region=AP/'",
        "analytics",
    )
    assert call == AddPartitionCall(
        sql=(
            "CALL system.register_partition("
            "'analytics','sales',ARRAY['region'],ARRAY['AP'],"
            "'s3://b/sales/region=AP/')"
        ),
        noop_if_exists=False,
    )


def test_if_not_exists_marks_the_noop_flag() -> None:
    call = add_partition_trino_call(
        "ALTER TABLE sales ADD IF NOT EXISTS PARTITION (region='AP') "
        "LOCATION 's3://b/x/'",
        "analytics",
    )
    assert call is not None
    assert call.noop_if_exists is True
    assert call.sql.startswith("CALL system.register_partition(")


@pytest.mark.parametrize(
    "target,expected",
    [
        # A qualified name wins over the request Database context.
        ("staging.sales", ("staging", "sales")),
        ("`staging`.`sales`", ("staging", "sales")),
        ('"staging"."sales"', ("staging", "sales")),
        ("SALES", ("analytics", "sales")),  # bare names fold lowercase
        ("sales", ("analytics", "sales")),
    ],
)
def test_schema_resolution(target: str, expected: tuple[str, str]) -> None:
    call = add_partition_trino_call(
        f"ALTER TABLE {target} ADD PARTITION (region='AP') "
        "LOCATION 's3://b/x/'",
        "analytics",
    )
    assert call is not None
    schema, table = expected
    assert f"'{schema}','{table}'," in call.sql


def test_omitted_location_drops_the_fifth_argument() -> None:
    call = add_partition_trino_call(
        "ALTER TABLE sales ADD PARTITION (region='AP')", "analytics"
    )
    assert call is not None
    assert call.sql == (
        "CALL system.register_partition("
        "'analytics','sales',ARRAY['region'],ARRAY['AP'])"
    )


def test_multi_key_spec_pairs_columns_with_values_in_order() -> None:
    call = add_partition_trino_call(
        "ALTER TABLE sales ADD PARTITION (region='AP', amount=9.5) "
        "LOCATION 's3://b/x/'",
        "analytics",
    )
    assert call is not None
    assert "ARRAY['region','amount'],ARRAY['AP','9.5']" in call.sql


def test_literal_escapes_round_trip() -> None:
    call = add_partition_trino_call(
        "ALTER TABLE sales ADD PARTITION (note='it''s') "
        "LOCATION 's3://b/o''h/'",
        "analytics",
    )
    assert call is not None
    assert "ARRAY['note'],ARRAY['it''s']" in call.sql
    assert call.sql.endswith("'s3://b/o''h/')")


def test_trailing_semicolon_is_consumed() -> None:
    call = add_partition_trino_call(
        "ALTER TABLE sales ADD PARTITION (region='AP');", "analytics"
    )
    assert call is not None
    assert call.sql.endswith("])")


def test_leading_whitespace_and_case_are_preserved() -> None:
    call = add_partition_trino_call(
        "  ALTER TABLE sales ADD PARTITION (region='AP')", "analytics"
    )
    assert call is not None
    assert call.sql.startswith("  CALL system.register_partition(")


@pytest.mark.parametrize(
    "query,database",
    [
        # Other ALTER TABLE forms are Trino's own grammar — leave them.
        ("ALTER TABLE sales ADD COLUMN c int", "analytics"),
        ("ALTER TABLE sales DROP COLUMN c", "analytics"),
        ("ALTER TABLE sales RENAME TO s2", "analytics"),
        # Not an ALTER TABLE ADD PARTITION at all.
        ("SELECT 1", "analytics"),
        ("MSCK REPAIR TABLE sales", "analytics"),
        ("SHOW PARTITIONS sales", "analytics"),
        # A catalog-qualified name is unresolvable — Trino rejects it.
        ("ALTER TABLE cat.db.sales ADD PARTITION (a='1')", "analytics"),
        # No schema anywhere: the procedure args can't resolve.
        ("ALTER TABLE sales ADD PARTITION (a='1')", None),
        # Specs that are not key='lit'|number pairs pass through too.
        ("ALTER TABLE sales ADD PARTITION (region)", "analytics"),
        ("ALTER TABLE sales ADD PARTITION ()", "analytics"),
        ("ALTER TABLE sales ADD PARTITION (region='AP') LOCATION", "a"),
        ("ALTER TABLE sales ADD PARTITION (a='1') garbage", "analytics"),
        # Unterminated literals or parens can't be trusted to a rewrite.
        ("ALTER TABLE sales ADD PARTITION (a='1'", "analytics"),
        ("ALTER TABLE sales ADD PARTITION (a='1) LOCATION 'x'", "a"),
    ],
)
def test_non_partition_or_malformed_statements_pass_through(
    query: str, database: str | None
) -> None:
    assert add_partition_trino_call(query, database) is None


@pytest.mark.parametrize(
    "query",
    [
        "ALTER TABLE sales ADD PARTITION (a='1') PARTITION (a='2')",
        "ALTER TABLE sales ADD IF NOT EXISTS PARTITION (a='1') "
        "LOCATION 's3://b/x/' PARTITION (a='2') LOCATION 's3://b/y/'",
    ],
)
def test_multiple_partition_clauses_reject_as_unrepresentable(
    query: str,
) -> None:
    """One Trino statement registers one partition; AWS-valid multi-PARTITION
    adds name the offender like external_table.py's unmappable clauses."""
    with pytest.raises(InvalidRequestException, match="PARTITION"):
        add_partition_trino_call(query, "analytics")
