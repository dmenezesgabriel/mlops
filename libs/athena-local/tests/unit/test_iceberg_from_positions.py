"""FROM positions that never open a table list must not reach Glue.

``EXTRACT(year FROM ts)``, ``TRIM(… FROM s)``, ``SUBSTRING(… FROM n)``,
and ``OVERLAY(… PLACING … FROM n)`` put a FROM keyword inside ``ident(…)``
call parens; ``a IS [NOT] DISTINCT FROM b`` uses it in a comparison
predicate; and ``FROM UNNEST(…)`` leads the table-item list with a call.
None of these is a table position — probing one against a colliding
Iceberg name emitted ``EXTRACT(year FROM iceberg."db"."ts")`` /
``iceberg."db"."unnest"(ARRAY[1])``, breaking legal statements.
"""

from __future__ import annotations

from athena_local.iceberg import iceberg_trino_submission
from tests.unit._iceberg_fakes import DATABASE, StaticIcebergProbe, route


class TestCallArgumentFromPositions:
    """A ``from`` inside ``ident(…)`` parens is a call argument, not a table."""

    ICE = {
        ("analytics", "ice_t"),
        ("analytics", "ts"),
        ("analytics", "s"),
        ("analytics", "start_i"),
    }

    def test_extract_from_argument_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT EXTRACT(year FROM ts) FROM ice_t", DATABASE, probe
        )
        assert sql == (
            'SELECT EXTRACT(year FROM ts) FROM iceberg."analytics"."ice_t"'
        )
        assert ("analytics", "ts") not in probe.calls

    def test_extract_qualified_argument_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT EXTRACT(year FROM u.ts) FROM ice_t", DATABASE, probe
        )
        assert sql == (
            'SELECT EXTRACT(year FROM u.ts) FROM iceberg."analytics"."ice_t"'
        )
        assert ("u", "ts") not in probe.calls

    def test_trim_leading_from_argument_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT TRIM(LEADING 'x' FROM s) FROM ice_t", DATABASE, probe
        )
        assert sql == (
            "SELECT TRIM(LEADING 'x' FROM s) "
            'FROM iceberg."analytics"."ice_t"'
        )
        assert ("analytics", "s") not in probe.calls

    def test_trim_both_from_argument_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT TRIM(BOTH 'x' FROM s) FROM ice_t", DATABASE, probe
        )
        assert sql == (
            'SELECT TRIM(BOTH \'x\' FROM s) FROM iceberg."analytics"."ice_t"'
        )

    def test_substring_from_argument_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT SUBSTRING(name FROM start_i) FROM ice_t",
            DATABASE,
            probe,
        )
        assert sql == (
            "SELECT SUBSTRING(name FROM start_i) "
            'FROM iceberg."analytics"."ice_t"'
        )
        assert ("analytics", "start_i") not in probe.calls

    def test_overlay_placing_from_argument_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT OVERLAY(name PLACING 'x' FROM start_i) FROM ice_t",
            DATABASE,
            probe,
        )
        assert sql == (
            "SELECT OVERLAY(name PLACING 'x' FROM start_i) "
            'FROM iceberg."analytics"."ice_t"'
        )
        assert ("analytics", "start_i") not in probe.calls

    def test_lowercase_call_argument_is_not_probed(self) -> None:
        sql = route("select extract(year from ts) from ice_t", self.ICE)
        assert sql == (
            'select extract(year from ts) from iceberg."analytics"."ice_t"'
        )

    def test_nested_subquery_inside_call_is_probed(self) -> None:
        # The inner ``(`` after ``((`` is not a call — its FROM anchors.
        sql = route("SELECT my_fn((SELECT 1 FROM ice_t)) FROM t", self.ICE)
        assert sql == (
            'SELECT my_fn((SELECT 1 FROM iceberg."analytics"."ice_t")) FROM t'
        )


class TestQueryParenContextsStillProbe:
    """A ``(`` after a query keyword still wraps a table context."""

    ICE = {("analytics", "ice_t")}

    def test_in_subquery_is_probed(self) -> None:
        sql = route(
            "SELECT x FROM t WHERE x IN (SELECT y FROM ice_t)", self.ICE
        )
        assert sql == (
            "SELECT x FROM t WHERE x IN "
            '(SELECT y FROM iceberg."analytics"."ice_t")'
        )

    def test_any_subquery_is_probed(self) -> None:
        sql = route(
            "SELECT x FROM t WHERE x = ANY (SELECT y FROM ice_t)", self.ICE
        )
        assert sql == (
            "SELECT x FROM t WHERE x = ANY "
            '(SELECT y FROM iceberg."analytics"."ice_t")'
        )

    def test_exists_subquery_is_probed(self) -> None:
        sql = route(
            "SELECT x FROM t WHERE EXISTS (SELECT 1 FROM ice_t)", self.ICE
        )
        assert sql == (
            "SELECT x FROM t WHERE EXISTS "
            '(SELECT 1 FROM iceberg."analytics"."ice_t")'
        )

    def test_cte_body_is_probed(self) -> None:
        sql = route(
            "WITH c AS (SELECT 1 FROM ice_t) SELECT * FROM c", self.ICE
        )
        assert sql == (
            'WITH c AS (SELECT 1 FROM iceberg."analytics"."ice_t") '
            "SELECT * FROM c"
        )

    def test_derived_table_is_probed(self) -> None:
        sql = route("SELECT * FROM (SELECT 1 FROM ice_t) d", self.ICE)
        assert sql == (
            'SELECT * FROM (SELECT 1 FROM iceberg."analytics"."ice_t") d'
        )

    def test_join_subquery_is_probed(self) -> None:
        sql = route(
            "SELECT * FROM t JOIN (SELECT 1 FROM ice_t) j ON true",
            self.ICE,
        )
        assert sql == (
            'SELECT * FROM t JOIN (SELECT 1 FROM iceberg."analytics"."ice_t")'
            " j ON true"
        )

    def test_merge_using_subquery_is_probed(self) -> None:
        sql = route(
            "MERGE INTO t USING (SELECT 1 FROM ice_t) s ON t.a = s.a "
            "WHEN MATCHED THEN DELETE",
            self.ICE,
        )
        assert sql == (
            "MERGE INTO t USING "
            '(SELECT 1 FROM iceberg."analytics"."ice_t") s ON t.a = s.a '
            "WHEN MATCHED THEN DELETE"
        )

    def test_unload_query_is_probed(self) -> None:
        sql = route(
            "UNLOAD (SELECT * FROM ice_t) TO 's3://b/u/' "
            "WITH (format='PARQUET')",
            self.ICE,
        )
        assert sql == (
            'UNLOAD (SELECT * FROM iceberg."analytics"."ice_t") '
            "TO 's3://b/u/' WITH (format='PARQUET')"
        )

    def test_scalar_select_is_probed(self) -> None:
        sql = route("SELECT (SELECT 1 FROM ice_t) v FROM t", self.ICE)
        assert sql == (
            'SELECT (SELECT 1 FROM iceberg."analytics"."ice_t") v FROM t'
        )


class TestLeadingCallItems:
    """The first table-item list entry may be a call, not a reference."""

    ICE = {("analytics", "unnest"), ("analytics", "ice_t")}

    def test_unnest_first_item_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        assert (
            iceberg_trino_submission(
                "SELECT * FROM UNNEST(ARRAY[1]) u", DATABASE, probe
            )
            is None
        )
        # A leading table function must never reach Glue.
        assert probe.calls == []

    def test_unnest_first_item_and_later_table(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT * FROM UNNEST(ARRAY[1]) u, ice_t", DATABASE, probe
        )
        assert sql == (
            'SELECT * FROM UNNEST(ARRAY[1]) u, iceberg."analytics"."ice_t"'
        )
        assert ("analytics", "unnest") not in probe.calls

    def test_cross_join_unnest_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT * FROM ice_t CROSS JOIN UNNEST(a) u", DATABASE, probe
        )
        assert sql == (
            'SELECT * FROM iceberg."analytics"."ice_t" CROSS JOIN UNNEST(a) u'
        )
        assert ("analytics", "unnest") not in probe.calls

    def test_insert_column_list_still_probes(self) -> None:
        # ``insert into`` keeps the plain first-item path: ``(a,b)`` after
        # the target is a column list, not a call.
        sql = route(
            "INSERT INTO ice_t (a, b) SELECT x, y FROM src",
            {("analytics", "ice_t")},
        )
        assert sql == (
            'INSERT INTO iceberg."analytics"."ice_t" (a, b) '
            "SELECT x, y FROM src"
        )

    def test_aliased_table_column_list_is_a_conservative_miss(self) -> None:
        # ``FROM t (a, b)`` is an aliased-table spelling the first-item
        # call-skip cannot tell from ``UNNEST(…)`` — the table goes
        # unprobed (missed route, never broken SQL), the same tradeoff
        # chained items already make.
        probe = StaticIcebergProbe(self.ICE)
        assert (
            iceberg_trino_submission(
                "SELECT * FROM ice_t (a, b)", DATABASE, probe
            )
            is None
        )
        assert probe.calls == []


class TestDistinctFromPredicate:
    """``a IS [NOT] DISTINCT FROM b`` — ``b`` is a value, never a table."""

    def test_is_distinct_from_is_not_probed(self) -> None:
        probe = StaticIcebergProbe({("analytics", "b")})
        assert (
            iceberg_trino_submission(
                "SELECT * FROM t WHERE a IS DISTINCT FROM b",
                DATABASE,
                probe,
            )
            is None
        )
        assert ("analytics", "b") not in probe.calls

    def test_is_not_distinct_from_is_not_probed(self) -> None:
        probe = StaticIcebergProbe({("analytics", "b")})
        assert (
            iceberg_trino_submission(
                "SELECT * FROM t WHERE a IS NOT DISTINCT FROM b",
                DATABASE,
                probe,
            )
            is None
        )
        assert ("analytics", "b") not in probe.calls

    def test_distinct_select_still_probes(self) -> None:
        # ``SELECT DISTINCT a`` — the ``distinct`` there is not a predicate.
        sql = route("SELECT DISTINCT a FROM ice_t", {("analytics", "ice_t")})
        assert sql == 'SELECT DISTINCT a FROM iceberg."analytics"."ice_t"'

    def test_bare_distinct_from_is_a_table_position(self) -> None:
        # A `DISTINCT` with nothing before it is not an IS [NOT] DISTINCT
        # predicate, so the FROM still opens a table list (G-267 arm).
        assert route("DISTINCT FROM ice_t", {("analytics", "ice_t")}) == (
            'DISTINCT FROM iceberg."analytics"."ice_t"'
        )

    def test_select_distinct_before_from_is_a_table_position(self) -> None:
        # No expression between SELECT DISTINCT and FROM: the preceding word
        # is neither `is` nor `not`, so the FROM is a table position.
        assert route(
            "SELECT DISTINCT FROM ice_t", {("analytics", "ice_t")}
        ) == ('SELECT DISTINCT FROM iceberg."analytics"."ice_t"')
