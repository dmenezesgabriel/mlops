"""Unit tests for ``iceberg.py`` — Athena Iceberg surface → ``iceberg``
catalog.

Athena registers Iceberg tables in Glue with ``Parameters.table_type=ICEBERG``
(AWS UG ``querying-iceberg-creating-tables.html``) and routes statements
touching them to its Iceberg engine; a hive view of such a table fails
``UNSUPPORTED_TABLE_TYPE`` (probed on the compose stack). The emulator
mirrors the routing with a dedicated ``iceberg`` Trino catalog over the same
moto Glue: TBLPROPERTIES-declared CREATEs map to
``CREATE TABLE iceberg."db"."t" … WITH(format, location[, partitioning])``,
Iceberg-targeted ALTERs convert Hive's ``ADD COLUMNS``/``CHANGE COLUMN`` to
Trino's single-action grammar, and every other statement gets its Iceberg
table references catalog-qualified — the exact shapes awswrangler emits
(``awswrangler/athena/_write_iceberg.py:108-113,246,258,410-426,871-877``).
"""

from __future__ import annotations

import time

from athena_local.glue_proxy import GlueProxy
from athena_local.iceberg import (
    iceberg_trino_submission,
)
from athena_local.iceberg_probe import GlueIcebergProbe
from tests.unit._glue_fakes import FakeGlueClient
from tests.unit._iceberg_fakes import DATABASE, StaticIcebergProbe, route


class TestIcebergRouting:
    ICE = {("analytics", "ice_t")}

    def test_insert_into_iceberg_target_is_qualified(self) -> None:
        sql = route(
            'INSERT INTO "analytics"."ice_t" ("id", "v") '
            'SELECT "id", "v" FROM "analytics"."temp_table_x"',
            self.ICE,
        )
        assert sql == (
            'INSERT INTO iceberg."analytics"."ice_t" ("id", "v") '
            'SELECT "id", "v" FROM "analytics"."temp_table_x"'
        )

    def test_merge_into_iceberg_target_keeps_hive_source(self) -> None:
        sql = route(
            'MERGE INTO "analytics"."ice_t" target '
            'USING "analytics"."temp_table_x" source '
            'ON target."id" = source."id" WHEN MATCHED THEN DELETE',
            self.ICE,
        )
        assert sql == (
            'MERGE INTO iceberg."analytics"."ice_t" target '
            'USING "analytics"."temp_table_x" source '
            'ON target."id" = source."id" WHEN MATCHED THEN DELETE'
        )

    def test_backticked_identifiers_normalize_to_double_quotes(self) -> None:
        # Trino rejects `` `ident` ``; Athena's DDL engine accepts it, which
        # is why consumers emit it — the iceberg path normalizes.
        sql = route(
            "MERGE INTO `analytics`.`ice_t` target "
            "USING `analytics`.`temp_table_x` source "
            "ON target.`id` = source.`id` WHEN MATCHED THEN DELETE",
            self.ICE,
        )
        assert sql == (
            'MERGE INTO iceberg."analytics"."ice_t" target '
            'USING "analytics"."temp_table_x" source '
            'ON target."id" = source."id" WHEN MATCHED THEN DELETE'
        )

    def test_delete_from_iceberg_table_is_qualified(self) -> None:
        sql = route('DELETE FROM "ice_t"', self.ICE)
        assert sql == 'DELETE FROM iceberg."analytics"."ice_t"'

    def test_select_from_iceberg_table_is_qualified(self) -> None:
        sql = route("SELECT * FROM ice_t", self.ICE)
        assert sql == 'SELECT * FROM iceberg."analytics"."ice_t"'

    def test_hive_table_references_pass_through(self) -> None:
        assert route("SELECT * FROM plain_t", set()) is None
        assert (
            route('INSERT INTO "analytics"."plain_t" SELECT 1', set()) is None
        )

    def test_join_on_iceberg_table_is_qualified(self) -> None:
        sql = route(
            "SELECT a.id FROM plain_t a JOIN ice_t b ON a.id = b.id",
            self.ICE,
        )
        assert sql == (
            "SELECT a.id FROM plain_t a "
            'JOIN iceberg."analytics"."ice_t" b ON a.id = b.id'
        )

    def test_subquery_references_are_qualified(self) -> None:
        sql = route(
            "DELETE FROM staging WHERE EXISTS (SELECT * FROM ice_t)",
            self.ICE,
        )
        assert sql is not None
        assert 'FROM iceberg."analytics"."ice_t"' in sql

    def test_cte_reference_is_left_alone(self) -> None:
        # A Glue lookup misses the CTE name, so the ref resolves as a CTE.
        assert (
            route("WITH ice_t AS (SELECT 1) SELECT * FROM ice_t", set())
            is None
        )

    def test_three_part_reference_passes_through(self) -> None:
        assert route("SELECT * FROM hive.analytics.ice_t", self.ICE) is None

    def test_table_function_is_left_alone(self) -> None:
        assert route("SELECT * FROM UNNEST(ARRAY[1,2])", set()) is None

    def test_string_literal_contents_are_untouched(self) -> None:
        sql = route("SELECT 'from ice_t' AS txt", self.ICE)
        assert sql is None

    def test_comment_contents_are_untouched(self) -> None:
        sql = route("SELECT 1 -- from ice_t", self.ICE)
        assert sql is None

    def test_insert_column_list_after_target_is_not_a_function(self) -> None:
        sql = route("INSERT INTO ice_t (a, b) SELECT x, y FROM src", self.ICE)
        assert sql == (
            'INSERT INTO iceberg."analytics"."ice_t" (a, b) '
            "SELECT x, y FROM src"
        )

    def test_missing_database_context_leaves_bare_reference(self) -> None:
        assert route("DELETE FROM ice_t", self.ICE, database=None) is None

    def test_describe_iceberg_table_is_qualified(self) -> None:
        sql = route("DESCRIBE `ice_t`;", self.ICE)
        assert sql == 'DESCRIBE iceberg."analytics"."ice_t";'

    def test_show_create_table_is_qualified(self) -> None:
        sql = route("SHOW CREATE TABLE `ice_t`", self.ICE)
        assert sql == 'SHOW CREATE TABLE iceberg."analytics"."ice_t"'

    def test_drop_table_is_qualified(self) -> None:
        sql = route("DROP TABLE `ice_t`", self.ICE)
        assert sql == 'DROP TABLE iceberg."analytics"."ice_t"'

    def test_truncate_table_is_qualified(self) -> None:
        sql = route("TRUNCATE TABLE `ice_t`", self.ICE)
        assert sql == 'TRUNCATE TABLE iceberg."analytics"."ice_t"'

    def test_update_is_qualified(self) -> None:
        sql = route('UPDATE ice_t SET "v" = 1 WHERE "id" = 2', self.ICE)
        assert sql == (
            'UPDATE iceberg."analytics"."ice_t" SET "v" = 1 WHERE "id" = 2'
        )

    def test_probe_runs_once_per_unique_table(self) -> None:
        probe = StaticIcebergProbe({("analytics", "ice_t")})
        iceberg_trino_submission(
            "SELECT * FROM ice_t a JOIN ice_t b ON a.id = b.id",
            DATABASE,
            probe,
        )
        assert probe.calls == [("analytics", "ice_t")]

    def test_keyword_inside_quoted_identifier_is_not_an_anchor(self) -> None:
        # A column literally named "from" must not open a table reference.
        assert (
            route('SELECT "from" FROM ice_t', self.ICE)
            == 'SELECT "from" FROM iceberg."analytics"."ice_t"'
        )

    def test_backtick_inside_quoted_identifier_is_preserved(self) -> None:
        sql = route('SELECT "don`t" FROM `ice_t`', self.ICE)
        assert sql == ('SELECT "don`t" FROM iceberg."analytics"."ice_t"')


class TestIcebergCommaItems:
    """Comma-separated FROM-list items share the anchor's route probe.

    Athena's grammar accepts implicit cross joins (``FROM a, b``); every
    item in the list is a table reference, so each must be probed — the
    anchor keyword only precedes the first (live-measured gap: ``FROM
    hive_t h, ice_t i`` left ``ice_t`` unqualified →
    ``UNSUPPORTED_TABLE_TYPE``).
    """

    ICE = {("analytics", "ice_t")}

    def test_comma_item_after_hive_table_is_qualified(self) -> None:
        sql = route(
            "SELECT * FROM hive_t h, ice_t i WHERE h.a = i.a", self.ICE
        )
        assert sql == (
            'SELECT * FROM hive_t h, iceberg."analytics"."ice_t" i '
            "WHERE h.a = i.a"
        )

    def test_each_item_in_three_list_is_probed(self) -> None:
        sql = route("SELECT * FROM a, ice_t, b", self.ICE)
        assert sql == 'SELECT * FROM a, iceberg."analytics"."ice_t", b'

    def test_comma_item_after_derived_table_is_probed(self) -> None:
        sql = route("SELECT * FROM (SELECT 1) x, ice_t", self.ICE)
        assert sql == (
            'SELECT * FROM (SELECT 1) x, iceberg."analytics"."ice_t"'
        )

    def test_comma_item_after_table_function_is_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT * FROM t, UNNEST(ARRAY[1]) u, ice_t", DATABASE, probe
        )
        assert sql == (
            'SELECT * FROM t, UNNEST(ARRAY[1]) u, iceberg."analytics"."ice_t"'
        )
        # UNNEST is a call, not a table ref — it must never reach Glue.
        assert ("analytics", "unnest") not in probe.calls

    def test_comma_items_with_as_aliases_are_probed(self) -> None:
        sql = route(
            "SELECT * FROM hive_t AS h, ice_t AS i WHERE h.a = i.a",
            self.ICE,
        )
        assert sql == (
            'SELECT * FROM hive_t AS h, iceberg."analytics"."ice_t" AS i '
            "WHERE h.a = i.a"
        )

    def test_comma_items_inside_subquery_are_probed(self) -> None:
        sql = route(
            "SELECT * FROM outer_t WHERE EXISTS (SELECT 1 FROM hive_t, ice_t)",
            self.ICE,
        )
        assert sql is not None
        assert 'FROM hive_t, iceberg."analytics"."ice_t"' in sql

    def test_comment_between_comma_and_item_is_skipped(self) -> None:
        sql = route("SELECT * FROM hive_t, -- note\n ice_t", self.ICE)
        assert sql == (
            'SELECT * FROM hive_t, -- note\n iceberg."analytics"."ice_t"'
        )

    def test_qualified_comma_item_is_probed(self) -> None:
        sql = route("SELECT * FROM h, analytics.ice_t", self.ICE)
        assert sql == ('SELECT * FROM h, iceberg."analytics"."ice_t"')

    def test_clause_commas_are_not_table_items(self) -> None:
        # GROUP BY's comma list must not be walked: the gap after an item
        # admits one alias token, then a comma — `GROUP` consumes the slot
        # and `BY` stops the walk.
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SELECT a, COUNT(*) FROM hive_t GROUP BY a, ice_t",
            DATABASE,
            probe,
        )
        assert sql is None
        assert ("analytics", "ice_t") not in probe.calls

    def test_update_set_commas_are_not_table_items(self) -> None:
        probe = StaticIcebergProbe(
            {("analytics", "ice_t"), ("analytics", "b")}
        )
        sql = iceberg_trino_submission(
            "UPDATE ice_t SET a = 1, b = 2 WHERE id = 3", DATABASE, probe
        )
        assert sql == (
            'UPDATE iceberg."analytics"."ice_t" SET a = 1, b = 2 WHERE id = 3'
        )
        assert ("analytics", "b") not in probe.calls


class TestShowSchemaArgs:
    """``SHOW <objects> FROM x`` — ``x`` names a schema/catalog, not a table.

    The bare ``from`` anchor also matches the FROM inside ``SHOW TABLES``-
    family spellings, whose argument is a schema or catalog: probing it as
    a table rewrote ``SHOW TABLES FROM ice_t`` to
    ``iceberg."db"."ice_t"`` whenever a colliding Iceberg table existed →
    Trino ``Too many parts in schema name`` where AWS answers
    schema-not-found (live-measured 2026-09-27 audit). ``SHOW COLUMNS
    FROM t`` stays probed — its argument IS the table.
    """

    ICE = {("analytics", "ice_t")}

    def test_show_tables_from_schema_arg_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        sql = iceberg_trino_submission(
            "SHOW TABLES FROM ice_t", DATABASE, probe
        )
        assert sql is None
        assert probe.calls == []

    def test_show_schema_family_args_are_not_probed(self) -> None:
        for statement in (
            "SHOW SCHEMAS FROM ice_t",
            "SHOW DATABASES FROM ice_t",
            "SHOW VIEWS FROM ice_t",
            "SHOW FUNCTIONS FROM ice_t",
            "SHOW ROLE GRANTS FROM ice_t",
        ):
            probe = StaticIcebergProbe(self.ICE)
            assert (
                iceberg_trino_submission(statement, DATABASE, probe) is None
            ), statement
            assert probe.calls == [], statement

    def test_show_tables_in_is_not_probed(self) -> None:
        probe = StaticIcebergProbe(self.ICE)
        assert (
            iceberg_trino_submission("SHOW TABLES IN ice_t", DATABASE, probe)
            is None
        )
        assert probe.calls == []

    def test_lowercase_show_tables_from_is_not_probed(self) -> None:
        assert route("show tables from ice_t", self.ICE) is None

    def test_comment_before_show_from_still_skips(self) -> None:
        assert route("SHOW TABLES /* note */ FROM ice_t", self.ICE) is None

    def test_show_columns_from_table_still_probes(self) -> None:
        # COLUMNS is the one SHOW object whose FROM argument is a table.
        sql = route("SHOW COLUMNS FROM ice_t", self.ICE)
        assert sql == 'SHOW COLUMNS FROM iceberg."analytics"."ice_t"'

    def test_noun_without_show_still_probes(self) -> None:
        sql = route("SELECT tables FROM ice_t", self.ICE)
        assert sql == 'SELECT tables FROM iceberg."analytics"."ice_t"'

    def test_column_show_aliased_tables_still_probes(self) -> None:
        # `show tables` in a select list is a `show` column with a `tables`
        # alias — not the SHOW TABLES statement.
        sql = route("SELECT show tables FROM ice_t", self.ICE)
        assert sql == ('SELECT show tables FROM iceberg."analytics"."ice_t"')

    def test_dotted_show_tables_name_still_probes(self) -> None:
        # `show.tables` is a schema-qualified table ref, not SHOW TABLES.
        sql = route("SELECT show.tables FROM ice_t", self.ICE)
        assert sql == ('SELECT show.tables FROM iceberg."analytics"."ice_t"')

    def test_explain_show_tables_from_is_not_probed(self) -> None:
        assert route("EXPLAIN SHOW TABLES FROM ice_t", self.ICE) is None


class TestIcebergDispatch:
    def test_no_iceberg_work_returns_none(self) -> None:
        assert (
            iceberg_trino_submission(
                "SELECT * FROM plain", DATABASE, StaticIcebergProbe(set())
            )
            is None
        )


class TestCacheInvalidation:
    """Catalog-mutating statements drop the probe's cross-statement cache.

    Every Glue write the emulator can cause arrives as a submitted
    statement, so a statement leading with ``CREATE``/``ALTER``/``DROP``/
    ``TRUNCATE`` empties the cached verdicts — the next probe re-reads
    Glue. Read statements (and DDL that never executes, like ``EXPLAIN`` or
    ``PREPARE`` bodies) leave the cache warm.
    """

    def test_leading_catalog_verbs_invalidate(self) -> None:
        for statement in (
            "CREATE TABLE t (id int)",
            "CREATE EXTERNAL TABLE t (id int) LOCATION 's3://b/t/'",
            "CREATE OR REPLACE TABLE t (id int)",
            "CREATE TABLE t AS SELECT 1",
            "CREATE DATABASE db2",
            "DROP TABLE t",
            "DROP TABLE IF EXISTS t",
            "DROP DATABASE db2 CASCADE",
            "DROP VIEW v",
            "ALTER TABLE t ADD COLUMNS (w double)",
            "TRUNCATE TABLE t",
            "create table t (id int)",
            "/* note */ CREATE TABLE t (id int)",
            "-- note\nDROP TABLE t",
            "SELECT 1; DROP TABLE t",
        ):
            probe = StaticIcebergProbe(set())
            iceberg_trino_submission(statement, DATABASE, probe)
            assert probe.invalidations == 1, statement

    def test_non_mutating_statements_keep_the_cache(self) -> None:
        for statement in (
            "SELECT * FROM t",
            "INSERT INTO t SELECT 1",
            "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE",
            "UPDATE t SET a = 1",
            "DELETE FROM t",
            "DESCRIBE t",
            "SHOW CREATE TABLE t",
            "SHOW TABLES FROM db",
            "MSCK REPAIR TABLE t",
            "UNLOAD (SELECT 1) TO 's3://b/u/' WITH (format='PARQUET')",
            "EXPLAIN CREATE TABLE t (id int)",
            "PREPARE s FROM DROP TABLE t",
            "WITH x AS (SELECT 1) SELECT * FROM x",
        ):
            probe = StaticIcebergProbe(set())
            iceberg_trino_submission(statement, DATABASE, probe)
            assert probe.invalidations == 0, statement

    def test_cached_verdict_survives_repeated_reads_across_statements(
        self,
    ) -> None:
        client = FakeGlueClient(
            tables={
                "analytics": [
                    {"Name": "t", "Parameters": {"table_type": "ICEBERG"}}
                ]
            }
        )
        probe = GlueIcebergProbe(GlueProxy(client))
        for _ in range(2):
            sql = iceberg_trino_submission("SELECT * FROM t", DATABASE, probe)
        assert sql == 'SELECT * FROM iceberg."analytics"."t"'
        assert client.get_table_calls == [("analytics", "t")]

    def test_drop_statement_clears_then_next_read_reprobes(self) -> None:
        tables = {
            "analytics": [
                {"Name": "t", "Parameters": {"table_type": "ICEBERG"}}
            ]
        }
        client = FakeGlueClient(tables=tables)
        probe = GlueIcebergProbe(GlueProxy(client))
        iceberg_trino_submission("SELECT * FROM t", DATABASE, probe)
        sql = iceberg_trino_submission("DROP TABLE t", DATABASE, probe)
        assert sql == 'DROP TABLE iceberg."analytics"."t"'
        # The drop lands in Glue through Trino — mirror it on the fake.
        tables.pop("analytics")
        assert (
            iceberg_trino_submission("SELECT * FROM t", DATABASE, probe)
            is None
        )
        assert client.get_table_calls == [("analytics", "t")] * 2

    def test_invalidated_create_target_reprobes_as_iceberg(self) -> None:
        # A name probed False as missing must route once a CREATE makes it
        # Iceberg — the create statement clears the stale verdict.
        tables: dict[str, list[dict[str, object]]] = {"analytics": []}
        client = FakeGlueClient(tables=tables)
        probe = GlueIcebergProbe(GlueProxy(client))
        assert (
            iceberg_trino_submission("SELECT * FROM t", DATABASE, probe)
            is None
        )
        iceberg_trino_submission(
            "CREATE TABLE t (id bigint) LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            DATABASE,
            probe,
        )
        tables["analytics"] = [
            {"Name": "t", "Parameters": {"table_type": "ICEBERG"}}
        ]
        sql = iceberg_trino_submission("SELECT * FROM t", DATABASE, probe)
        assert sql == 'SELECT * FROM iceberg."analytics"."t"'


class TestIcebergRoutingScaling:
    """The routing walk stays linear in comment count (G-266 / AU-23 D2).

    The old ``_covering_span`` rescanned the comment-span list from index 0
    on every ``_past_noise``/``_noise_back``/``_inside`` call, so a
    comment-heavy ``FROM a, b, …`` measured O(refs × comments): 585 ms at
    10³ comments and 32.6 s at 10⁴. Pre-sorting the spans once and
    bisecting makes each lookup O(log comments).
    """

    ICE = {("analytics", "ice_t")}

    def test_comment_heavy_from_list_stays_linear(self) -> None:
        # The index-0 rescan made the comment-heavy walk ~55× the plain-ref
        # walk at this size (1549 ms vs 28 ms); bisecting holds both to a
        # small constant factor. The ratio keeps the bound independent of
        # machine speed, unlike an absolute wall-clock ceiling.
        reference_count = 2000
        plain = "SELECT * FROM " + "ice_t, " * reference_count + "ice_t"
        commented = (
            "SELECT * FROM " + "ice_t -- pad\n, " * reference_count + "ice_t"
        )
        baseline_sql, baseline_ms = _route_with_elapsed_ms(plain, self.ICE)
        commented_sql, commented_ms = _route_with_elapsed_ms(
            commented, self.ICE
        )
        qualified = 'iceberg."analytics"."ice_t"'
        assert baseline_sql is not None
        assert baseline_sql.count(qualified) == reference_count + 1
        assert commented_sql is not None
        assert commented_sql.count(qualified) == reference_count + 1
        assert commented_ms < baseline_ms * 6


def _route_with_elapsed_ms(
    query: str, iceberg_tables: set[tuple[str, str]]
) -> tuple[str | None, float]:
    start = time.perf_counter()
    sql = route(query, iceberg_tables)
    return sql, (time.perf_counter() - start) * 1000
