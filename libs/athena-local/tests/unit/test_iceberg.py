"""Unit tests for ``iceberg.py`` — Athena Iceberg surface → ``iceberg`` catalog.

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

import pytest
from athena_local.errors import InvalidRequestException
from athena_local.glue_proxy import GlueProxy
from athena_local.iceberg import (
    GlueIcebergProbe,
    iceberg_trino_submission,
)
from tests.unit._glue_fakes import FakeGlueClient

DATABASE = "analytics"


class StaticIcebergProbe:
    """Named probe fake: reports the (database, table) set it is seeded with."""

    def __init__(self, iceberg_tables: set[tuple[str, str]]) -> None:
        self._iceberg_tables = iceberg_tables
        self.calls: list[tuple[str, str]] = []

    def is_iceberg_table(self, database: str, table: str) -> bool:
        self.calls.append((database, table))
        return (database, table) in self._iceberg_tables


def _route(
    query: str,
    iceberg_tables: set[tuple[str, str]],
    database: str | None = DATABASE,
) -> str | None:
    return iceberg_trino_submission(
        query, database, StaticIcebergProbe(iceberg_tables)
    )


class TestGlueIcebergProbe:
    def _probe(
        self, tables: dict[str, list[dict[str, object]]]
    ) -> GlueIcebergProbe:
        return GlueIcebergProbe(GlueProxy(FakeGlueClient(tables=tables)))

    def test_table_type_iceberg_is_detected(self) -> None:
        probe = self._probe(
            {
                "analytics": [
                    {"Name": "t", "Parameters": {"table_type": "ICEBERG"}}
                ]
            }
        )
        assert probe.is_iceberg_table("analytics", "t") is True

    def test_table_type_value_matches_case_insensitively(self) -> None:
        probe = self._probe(
            {
                "analytics": [
                    {"Name": "t", "Parameters": {"table_type": "iceberg"}}
                ]
            }
        )
        assert probe.is_iceberg_table("analytics", "t") is True

    def test_missing_table_is_not_iceberg(self) -> None:
        probe = self._probe({})
        assert probe.is_iceberg_table("analytics", "t") is False

    def test_table_without_parameters_is_not_iceberg(self) -> None:
        probe = self._probe({"analytics": [{"Name": "t"}]})
        assert probe.is_iceberg_table("analytics", "t") is False

    def test_hive_table_parameters_are_not_iceberg(self) -> None:
        probe = self._probe(
            {"analytics": [{"Name": "t", "Parameters": {"EXTERNAL": "TRUE"}}]}
        )
        assert probe.is_iceberg_table("analytics", "t") is False


class TestIcebergCreate:
    def test_create_table_maps_to_iceberg_catalog(self) -> None:
        sql = _route(
            "CREATE TABLE `t` (`id` bigint, `v` string) "
            "LOCATION 's3://b/ice/t/' "
            "TBLPROPERTIES ('table_type' ='ICEBERG', 'format'='parquet')",
            set(),
        )
        assert sql == (
            'CREATE TABLE iceberg."analytics"."t" '
            '("id" bigint, "v" varchar) '
            "WITH (format='PARQUET', location='s3://b/ice/t/')"
        )

    def test_if_not_exists_is_preserved(self) -> None:
        sql = _route(
            "CREATE TABLE IF NOT EXISTS `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "CREATE TABLE IF NOT EXISTS iceberg." in sql

    def test_qualified_name_wins_over_request_database(self) -> None:
        sql = _route(
            "CREATE TABLE `staging`.`t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert 'iceberg."staging"."t"' in sql

    def test_format_defaults_to_parquet(self) -> None:
        sql = _route(
            "CREATE TABLE `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "format='PARQUET'" in sql

    def test_format_value_folds_to_trino_enum(self) -> None:
        sql = _route(
            "CREATE TABLE `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG', 'format'='orc')",
            set(),
        )
        assert sql is not None
        assert "format='ORC'" in sql

    def test_unknown_format_value_rejects(self) -> None:
        with pytest.raises(InvalidRequestException, match="csv"):
            _route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG', 'format'='csv')",
                set(),
            )

    def test_partition_transforms_reorder_to_trino_spelling(self) -> None:
        # Athena writes bucket(N, col)/truncate(N, col); Trino's partitioning
        # strings take (col, N) — probed against the coordinator.
        sql = _route(
            "CREATE TABLE `t` (`id` bigint, `ts` timestamp, `cat` string) "
            "PARTITIONED BY (cat, bucket(16, id), day(ts), truncate(3, cat)) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert (
            "partitioning=ARRAY['cat','bucket(id, 16)','day(ts)',"
            "'truncate(cat, 3)']"
        ) in sql

    def test_table_comment_is_carried(self) -> None:
        sql = _route(
            "CREATE TABLE `t` (`id` bigint) "
            "COMMENT 'ice table' "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "COMMENT 'ice table'" in sql

    def test_column_comment_is_carried(self) -> None:
        sql = _route(
            "CREATE TABLE `t` (`id` bigint COMMENT 'pk') "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "\"id\" bigint COMMENT 'pk'" in sql

    def test_athena_only_tblproperties_are_dropped(self) -> None:
        # AWS's optimization/compression hints have no Trino WITH property.
        sql = _route(
            "CREATE TABLE `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG', "
            "'write_compression'='snappy', "
            "'optimize_rewrite_data_file_threshold'='10', "
            "'vacuum_min_snapshots_to_keep'='3')",
            set(),
        )
        assert sql is not None
        assert "compression" not in sql
        assert "optimize" not in sql
        assert "vacuum" not in sql

    def test_unknown_tblproperty_rejects_like_aws(self) -> None:
        # Athena restricts Iceberg TBLPROPERTIES to a predefined list.
        with pytest.raises(InvalidRequestException, match="bogus_prop"):
            _route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG', 'bogus_prop'='x')",
                set(),
            )

    def test_missing_location_rejects(self) -> None:
        with pytest.raises(InvalidRequestException, match="LOCATION"):
            _route(
                "CREATE TABLE `t` (`id` bigint) "
                "TBLPROPERTIES ('table_type'='ICEBERG')",
                set(),
            )

    def test_non_iceberg_tblproperties_passes_through(self) -> None:
        assert (
            _route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='HIVE')",
                set(),
            )
            is None
        )

    def test_create_without_tblproperties_passes_through(self) -> None:
        assert (
            _route(
                "CREATE TABLE `t` (`id` bigint) LOCATION 's3://b/t/'",
                set(),
            )
            is None
        )

    def test_non_create_passes_through(self) -> None:
        assert _route("SELECT 1", set()) is None
        assert (
            _route(
                "CREATE EXTERNAL TABLE `t` (`id` bigint) LOCATION 's3://b/' "
                "TBLPROPERTIES ('table_type'='ICEBERG')",
                set(),
            )
            is None
        )

    def test_unresolvable_schema_passes_through(self) -> None:
        assert (
            _route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG')",
                set(),
                database=None,
            )
            is None
        )

    def test_three_part_target_passes_through(self) -> None:
        assert (
            _route(
                "CREATE TABLE `cat`.`db`.`t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG')",
                set(),
            )
            is None
        )


class TestIcebergAlter:
    ICE = {("analytics", "t")}

    def test_add_columns_maps_single_column(self) -> None:
        sql = _route("ALTER TABLE `t` ADD COLUMNS (`w` double)", self.ICE)
        assert sql == (
            'ALTER TABLE iceberg."analytics"."t" ADD COLUMN "w" double'
        )

    def test_add_columns_with_many_columns_rejects(self) -> None:
        # Trino allows one action per ALTER TABLE (probed), so the AWS-valid
        # multi-column form cannot run as a single statement.
        with pytest.raises(InvalidRequestException, match="ADD COLUMNS"):
            _route(
                "ALTER TABLE `t` ADD COLUMNS (`w` double, `n` integer)",
                self.ICE,
            )

    def test_change_column_maps_to_set_data_type(self) -> None:
        sql = _route("ALTER TABLE `t` CHANGE COLUMN `v` `v` string", self.ICE)
        assert sql == (
            'ALTER TABLE iceberg."analytics"."t" '
            'ALTER COLUMN "v" SET DATA TYPE varchar'
        )

    def test_change_column_rename_rejects(self) -> None:
        # Renaming needs its own ALTER action; one submission, one action.
        with pytest.raises(InvalidRequestException, match="CHANGE COLUMN"):
            _route("ALTER TABLE `t` CHANGE COLUMN `v` `v2` string", self.ICE)

    def test_alter_on_hive_table_passes_through(self) -> None:
        assert (
            _route("ALTER TABLE `t` ADD COLUMNS (`w` double)", set()) is None
        )

    def test_other_alter_clauses_route_verbatim(self) -> None:
        sql = _route("ALTER TABLE `t` RENAME TO `t2`", self.ICE)
        assert sql == 'ALTER TABLE iceberg."analytics"."t" RENAME TO "t2"'


class TestIcebergRouting:
    ICE = {("analytics", "ice_t")}

    def test_insert_into_iceberg_target_is_qualified(self) -> None:
        sql = _route(
            'INSERT INTO "analytics"."ice_t" ("id", "v") '
            'SELECT "id", "v" FROM "analytics"."temp_table_x"',
            self.ICE,
        )
        assert sql == (
            'INSERT INTO iceberg."analytics"."ice_t" ("id", "v") '
            'SELECT "id", "v" FROM "analytics"."temp_table_x"'
        )

    def test_merge_into_iceberg_target_keeps_hive_source(self) -> None:
        sql = _route(
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
        sql = _route(
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
        sql = _route('DELETE FROM "ice_t"', self.ICE)
        assert sql == 'DELETE FROM iceberg."analytics"."ice_t"'

    def test_select_from_iceberg_table_is_qualified(self) -> None:
        sql = _route("SELECT * FROM ice_t", self.ICE)
        assert sql == 'SELECT * FROM iceberg."analytics"."ice_t"'

    def test_hive_table_references_pass_through(self) -> None:
        assert _route("SELECT * FROM plain_t", set()) is None
        assert (
            _route('INSERT INTO "analytics"."plain_t" SELECT 1', set()) is None
        )

    def test_join_on_iceberg_table_is_qualified(self) -> None:
        sql = _route(
            "SELECT a.id FROM plain_t a JOIN ice_t b ON a.id = b.id",
            self.ICE,
        )
        assert sql == (
            "SELECT a.id FROM plain_t a "
            'JOIN iceberg."analytics"."ice_t" b ON a.id = b.id'
        )

    def test_subquery_references_are_qualified(self) -> None:
        sql = _route(
            "DELETE FROM staging WHERE EXISTS (SELECT * FROM ice_t)",
            self.ICE,
        )
        assert sql is not None
        assert 'FROM iceberg."analytics"."ice_t"' in sql

    def test_cte_reference_is_left_alone(self) -> None:
        # A Glue lookup misses the CTE name, so the ref resolves as a CTE.
        assert (
            _route("WITH ice_t AS (SELECT 1) SELECT * FROM ice_t", set())
            is None
        )

    def test_three_part_reference_passes_through(self) -> None:
        assert _route("SELECT * FROM hive.analytics.ice_t", self.ICE) is None

    def test_table_function_is_left_alone(self) -> None:
        assert _route("SELECT * FROM UNNEST(ARRAY[1,2])", set()) is None

    def test_string_literal_contents_are_untouched(self) -> None:
        sql = _route("SELECT 'from ice_t' AS txt", self.ICE)
        assert sql is None

    def test_comment_contents_are_untouched(self) -> None:
        sql = _route("SELECT 1 -- from ice_t", self.ICE)
        assert sql is None

    def test_insert_column_list_after_target_is_not_a_function(self) -> None:
        sql = _route("INSERT INTO ice_t (a, b) SELECT x, y FROM src", self.ICE)
        assert sql == (
            'INSERT INTO iceberg."analytics"."ice_t" (a, b) '
            "SELECT x, y FROM src"
        )

    def test_missing_database_context_leaves_bare_reference(self) -> None:
        assert _route("DELETE FROM ice_t", self.ICE, database=None) is None

    def test_describe_iceberg_table_is_qualified(self) -> None:
        sql = _route("DESCRIBE `ice_t`;", self.ICE)
        assert sql == 'DESCRIBE iceberg."analytics"."ice_t";'

    def test_show_create_table_is_qualified(self) -> None:
        sql = _route("SHOW CREATE TABLE `ice_t`", self.ICE)
        assert sql == 'SHOW CREATE TABLE iceberg."analytics"."ice_t"'

    def test_drop_table_is_qualified(self) -> None:
        sql = _route("DROP TABLE `ice_t`", self.ICE)
        assert sql == 'DROP TABLE iceberg."analytics"."ice_t"'

    def test_truncate_table_is_qualified(self) -> None:
        sql = _route("TRUNCATE TABLE `ice_t`", self.ICE)
        assert sql == 'TRUNCATE TABLE iceberg."analytics"."ice_t"'

    def test_update_is_qualified(self) -> None:
        sql = _route('UPDATE ice_t SET "v" = 1 WHERE "id" = 2', self.ICE)
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
            _route('SELECT "from" FROM ice_t', self.ICE)
            == 'SELECT "from" FROM iceberg."analytics"."ice_t"'
        )

    def test_backtick_inside_quoted_identifier_is_preserved(self) -> None:
        sql = _route('SELECT "don`t" FROM `ice_t`', self.ICE)
        assert sql == ('SELECT "don`t" FROM iceberg."analytics"."ice_t"')


class TestIcebergDispatch:
    def test_no_iceberg_work_returns_none(self) -> None:
        assert (
            iceberg_trino_submission(
                "SELECT * FROM plain", DATABASE, StaticIcebergProbe(set())
            )
            is None
        )
