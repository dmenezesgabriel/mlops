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

import pytest
from athena_local.errors import InvalidRequestException
from tests.unit._iceberg_fakes import route


class TestIcebergCreate:
    def test_create_table_maps_to_iceberg_catalog(self) -> None:
        sql = route(
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
        sql = route(
            "CREATE TABLE IF NOT EXISTS `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "CREATE TABLE IF NOT EXISTS iceberg." in sql

    def test_qualified_name_wins_over_request_database(self) -> None:
        sql = route(
            "CREATE TABLE `staging`.`t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert 'iceberg."staging"."t"' in sql

    def test_format_defaults_to_parquet(self) -> None:
        sql = route(
            "CREATE TABLE `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "format='PARQUET'" in sql

    def test_format_value_folds_to_trino_enum(self) -> None:
        sql = route(
            "CREATE TABLE `t` (`id` bigint) "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG', 'format'='orc')",
            set(),
        )
        assert sql is not None
        assert "format='ORC'" in sql

    def test_unknown_format_value_rejects(self) -> None:
        with pytest.raises(InvalidRequestException, match="csv"):
            route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG', 'format'='csv')",
                set(),
            )

    def test_partition_transforms_reorder_to_trino_spelling(self) -> None:
        # Athena writes bucket(N, col)/truncate(N, col); Trino's partitioning
        # strings take (col, N) — probed against the coordinator.
        sql = route(
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
        sql = route(
            "CREATE TABLE `t` (`id` bigint) "
            "COMMENT 'ice table' "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "COMMENT 'ice table'" in sql

    def test_column_comment_is_carried(self) -> None:
        sql = route(
            "CREATE TABLE `t` (`id` bigint COMMENT 'pk') "
            "LOCATION 's3://b/t/' "
            "TBLPROPERTIES ('table_type'='ICEBERG')",
            set(),
        )
        assert sql is not None
        assert "\"id\" bigint COMMENT 'pk'" in sql

    def test_athena_only_tblproperties_are_dropped(self) -> None:
        # AWS's optimization/compression hints have no Trino WITH property.
        sql = route(
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
            route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='ICEBERG', 'bogus_prop'='x')",
                set(),
            )

    def test_missing_location_rejects(self) -> None:
        with pytest.raises(InvalidRequestException, match="LOCATION"):
            route(
                "CREATE TABLE `t` (`id` bigint) "
                "TBLPROPERTIES ('table_type'='ICEBERG')",
                set(),
            )

    def test_non_iceberg_tblproperties_passes_through(self) -> None:
        assert (
            route(
                "CREATE TABLE `t` (`id` bigint) "
                "LOCATION 's3://b/t/' "
                "TBLPROPERTIES ('table_type'='HIVE')",
                set(),
            )
            is None
        )

    def test_create_without_tblproperties_passes_through(self) -> None:
        assert (
            route(
                "CREATE TABLE `t` (`id` bigint) LOCATION 's3://b/t/'",
                set(),
            )
            is None
        )

    def test_non_create_passes_through(self) -> None:
        assert route("SELECT 1", set()) is None
        assert (
            route(
                "CREATE EXTERNAL TABLE `t` (`id` bigint) LOCATION 's3://b/' "
                "TBLPROPERTIES ('table_type'='ICEBERG')",
                set(),
            )
            is None
        )

    def test_unresolvable_schema_passes_through(self) -> None:
        assert (
            route(
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
            route(
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
        sql = route("ALTER TABLE `t` ADD COLUMNS (`w` double)", self.ICE)
        assert sql == (
            'ALTER TABLE iceberg."analytics"."t" ADD COLUMN "w" double'
        )

    def test_add_columns_with_many_columns_rejects(self) -> None:
        # Trino allows one action per ALTER TABLE (probed), so the AWS-valid
        # multi-column form cannot run as a single statement.
        with pytest.raises(InvalidRequestException, match="ADD COLUMNS"):
            route(
                "ALTER TABLE `t` ADD COLUMNS (`w` double, `n` integer)",
                self.ICE,
            )

    def test_change_column_maps_to_set_data_type(self) -> None:
        sql = route("ALTER TABLE `t` CHANGE COLUMN `v` `v` string", self.ICE)
        assert sql == (
            'ALTER TABLE iceberg."analytics"."t" '
            'ALTER COLUMN "v" SET DATA TYPE varchar'
        )

    def test_change_column_rename_rejects(self) -> None:
        # Renaming needs its own ALTER action; one submission, one action.
        with pytest.raises(InvalidRequestException, match="CHANGE COLUMN"):
            route("ALTER TABLE `t` CHANGE COLUMN `v` `v2` string", self.ICE)

    def test_alter_on_hive_table_passes_through(self) -> None:
        assert route("ALTER TABLE `t` ADD COLUMNS (`w` double)", set()) is None

    def test_other_alter_clauses_route_verbatim(self) -> None:
        sql = route("ALTER TABLE `t` RENAME TO `t2`", self.ICE)
        assert sql == 'ALTER TABLE iceberg."analytics"."t" RENAME TO "t2"'
