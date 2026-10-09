"""Unit tests for the SQL-rewrite entry seam (G-261, G-264).

``SubmissionPlanner._map_statement`` is the single production entry that
feeds UNLOAD / ADD PARTITION / Iceberg / dialect rewrites. A comment whose
text carries ``(`/`)`` — or any comment before UNLOAD's ``TO`` — used to
bail the rewrites to pass-through (or, on the Iceberg DDL surface, mis-parse
``PARTITIONED BY`` comment fragments into partition columns), because the
clause scanners only skip string literals. The deterministic rewrites are
asserted equal to their no-comment control, which the audit verified
rewrites (G-261: "canonical no-comment controls all rewrite"; G-264);
UNLOAD's temp-table token is a fresh UUID, so that one pins the rewrite
contract instead.
"""

from __future__ import annotations

import pytest
from athena_local.executions import ExecutionStore
from athena_local.iceberg_probe import IcebergTableProbe
from athena_local.submission import SubmissionPlanner, _MappedSubmission
from tests.unit._executor_fakes import ScriptedStatementClient
from tests.unit._iceberg_fakes import StaticIcebergProbe

DATABASE = "analytics"


def _plan(iceberg_probe: IcebergTableProbe | None = None) -> SubmissionPlanner:
    """Planner for the rewrite seam; store/client are never consulted here."""
    return SubmissionPlanner(
        store=ExecutionStore(),
        client=ScriptedStatementClient(pages=[]),
        iceberg_probe=iceberg_probe,
    )


def _mapped(planner: SubmissionPlanner, query: str) -> _MappedSubmission:
    return planner._map_statement(query, DATABASE)


def _assert_rewrites_like_control(
    planner: SubmissionPlanner,
    control: str,
    commented: str,
    guard: str,
) -> None:
    """The control rewrites (non-tautology guard), and the comment maps to it."""
    expected = _mapped(planner, control)
    assert guard in expected.sql, (
        f"control did not rewrite — expected {guard!r} in {expected.sql!r}"
    )
    assert _mapped(planner, commented) == expected, (
        f"comment variant diverged from control:\n"
        f"control:   {expected.sql!r}\n"
        f"commented: {_mapped(planner, commented).sql!r}"
    )


@pytest.mark.parametrize(
    "commented",
    [
        "CREATE EXTERNAL TABLE t (a int /* ) */) LOCATION 's3://b/x/'",
        "CREATE EXTERNAL TABLE t (a int -- )\n) LOCATION 's3://b/x/'",
    ],
)
def test_external_table_comment_bearing_spec_rewrites_like_control(
    commented: str,
) -> None:
    _assert_rewrites_like_control(
        _plan(),
        "CREATE EXTERNAL TABLE t (a int) LOCATION 's3://b/x/'",
        commented,
        "WITH (format='TEXTFILE', external_location='s3://b/x/')",
    )


@pytest.mark.parametrize(
    "commented",
    [
        "UNLOAD (SELECT 1) /* x */ TO 's3://b/u/' WITH (format='PARQUET')",
        "UNLOAD (SELECT 1) -- x\nTO 's3://b/u/' WITH (format='PARQUET')",
    ],
)
def test_unload_comment_before_to_still_rewrites_to_ctas(
    commented: str,
) -> None:
    """Comment-before-TO must not bail the rewrite (G-261's ``→ None``).

    ``_map_statement`` is not byte-deterministic for UNLOAD — the temp-table
    token is a fresh ``uuid4`` (dialect.py:286) — so the pin is the rewrite
    contract: a CTAS at the TO path whose table the record's cleanup flag
    names (dropped after completion).
    """
    planner = _plan()
    mapped = _mapped(planner, commented)
    assert mapped.unload_cleanup_table is not None, (
        "comment-before-TO bailed to pass-through"
    )
    assert (
        "WITH (format='PARQUET', external_location='s3://b/u/') AS SELECT 1"
        in mapped.sql
    )
    schema, table = mapped.unload_cleanup_table
    assert f'"{schema}"."{table}"' in mapped.sql


@pytest.mark.parametrize(
    "commented",
    [
        "ALTER TABLE sales ADD PARTITION (region='AP' /* ) */)",
        "ALTER TABLE sales ADD PARTITION (region='AP' -- )\n)",
    ],
)
def test_add_partition_comment_in_spec_rewrites_like_control(
    commented: str,
) -> None:
    _assert_rewrites_like_control(
        _plan(),
        "ALTER TABLE sales ADD PARTITION (region='AP')",
        commented,
        "CALL system.register_partition(",
    )


@pytest.mark.parametrize(
    "commented",
    [
        "CREATE TABLE t (id bigint /* ) */) LOCATION 's3://b/t/' "
        "TBLPROPERTIES ('table_type'='ICEBERG')",
        "CREATE TABLE t (id bigint -- )\n) LOCATION 's3://b/t/' "
        "TBLPROPERTIES ('table_type'='ICEBERG')",
        "CREATE TABLE t (id bigint) /* between */ LOCATION 's3://b/t/' "
        "TBLPROPERTIES ('table_type'='ICEBERG')",
        "CREATE TABLE t (id bigint) LOCATION 's3://b/t/' "
        "/* tblprops */ TBLPROPERTIES ('table_type'='ICEBERG')",
    ],
)
def test_iceberg_create_comment_bearing_spec_rewrites_like_control(
    commented: str,
) -> None:
    _assert_rewrites_like_control(
        _plan(iceberg_probe=StaticIcebergProbe(set())),
        (
            "CREATE TABLE t (id bigint) LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')"
        ),
        commented,
        'iceberg."analytics".',
    )


def test_iceberg_partitioned_by_comment_fragments_do_not_become_columns() -> (
    None
):
    """The G-264 mis-rewrite: ``cat /* , */ , bucket(16, id)`` split cleanly."""
    mapped = _mapped(
        _plan(iceberg_probe=StaticIcebergProbe(set())),
        "CREATE TABLE t (id bigint, cat string) "
        "PARTITIONED BY (cat /* , */ , bucket(16, id)) "
        "LOCATION 's3://b/t/' TBLPROPERTIES ('table_type'='ICEBERG')",
    )
    assert "partitioning=ARRAY['cat','bucket(id, 16)']" in mapped.sql
