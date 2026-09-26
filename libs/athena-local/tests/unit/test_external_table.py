"""Unit tests for the ``CREATE EXTERNAL TABLE`` dialect map.

Athena's Hive-DDL spelling — ``CREATE EXTERNAL TABLE [db.]t (cols) [PARTITIONED
BY] [CLUSTERED BY] [ROW FORMAT] STORED AS … LOCATION 's3://…' [TBLPROPERTIES]``
(docs.aws.amazon.com/athena/latest/ug/create-table.html) — has no Trino 483
form at all (the coordinator rejects ``EXTERNAL`` outright). The rewrite emits
Trino's ``CREATE TABLE … WITH(format, external_location, partitioned_by, …)``;
the stored ``QueryExecution.Query`` keeps the original Athena text. Tested
through ``to_trino_dialect`` like the sibling rules (test_dialect.py).
"""

from __future__ import annotations

import pytest
from athena_local.dialect import to_trino_dialect
from athena_local.errors import InvalidRequestException


def test_minimal_external_table_maps_to_trino_with_clause() -> None:
    """The nb05 boundary probe's exact statement shape."""
    query = (
        "CREATE EXTERNAL TABLE ext_sales (id bigint, item string)\n"
        "STORED AS PARQUET\n"
        "LOCATION 's3://bucket/ext/'"
    )
    assert to_trino_dialect(query, "analytics") == (
        'CREATE TABLE "analytics"."ext_sales" '
        '("id" bigint, "item" varchar) '
        "WITH (format='PARQUET', external_location='s3://bucket/ext/')"
    )


def test_wrangler_generated_ddl_full_clause_set() -> None:
    """``generate_create_query``'s exact emission (_utils.py:1076-1092)."""
    query = (
        "CREATE EXTERNAL TABLE `sales`(\n"
        "  `quantity` bigint, \n"
        "  `amount` double)\n"
        "PARTITIONED BY ( \n"
        "  `region` string)\n"
        "ROW FORMAT SERDE \n"
        "  'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe' \n"
        "STORED AS INPUTFORMAT \n"
        "  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat' \n"
        "OUTPUTFORMAT \n"
        "  'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat'\n"
        "LOCATION\n"
        "  's3://bucket/datasets/sales/'\n"
        "TBLPROPERTIES (\n"
        "  'classification'='parquet', \n"
        "  'compressionType'='snappy', \n"
        "  'typeOfData'='file', \n"
        "  'projection.enabled'='false')"
    )
    assert to_trino_dialect(query, "analytics") == (
        'CREATE TABLE "analytics"."sales" '
        '("quantity" bigint, "amount" double, "region" varchar) '
        "WITH (format='PARQUET', "
        "external_location='s3://bucket/datasets/sales/', "
        "partitioned_by=ARRAY['region'])"
    )


@pytest.mark.parametrize(
    "query,database,expected",
    [
        # IF NOT EXISTS and the optional schema qualifier carry over.
        (
            "CREATE EXTERNAL TABLE IF NOT EXISTS db.sales (a int) "
            "STORED AS ORC LOCATION 's3://b/x/'",
            "other",
            'CREATE TABLE IF NOT EXISTS "db"."sales" ("a" int) '
            "WITH (format='ORC', external_location='s3://b/x/')",
        ),
        # An unqualified name falls back to the request's Database context.
        (
            "create external table sales (a int) "
            "stored as parquet location 's3://b/x/'",
            "analytics",
            'CREATE TABLE "analytics"."sales" ("a" int) '
            "WITH (format='PARQUET', external_location='s3://b/x/')",
        ),
        # No schema and no Database context: emit the bare name so Trino's
        # own session-schema error surfaces.
        (
            "CREATE EXTERNAL TABLE sales (a int) "
            "STORED AS PARQUET LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "sales" ("a" int) '
            "WITH (format='PARQUET', external_location='s3://b/x/')",
        ),
        # Quoted identifiers keep their case; bare ones fold.
        (
            'CREATE EXTERNAL TABLE "Db"."Sales" (a int) '
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "Db"."Sales" ("a" int) '
            "WITH (format='TEXTFILE', external_location='s3://b/x/')",
        ),
        (
            "CREATE EXTERNAL TABLE `Sales` (`Q` double) "
            "STORED AS AVRO LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "Sales" ("Q" double) '
            "WITH (format='AVRO', external_location='s3://b/x/')",
        ),
        # Leading whitespace is preserved.
        (
            "  CREATE EXTERNAL TABLE s (a int) "
            "STORED AS JSON LOCATION 's3://b/x/'",
            None,
            '  CREATE TABLE "s" ("a" int) '
            "WITH (format='JSON', external_location='s3://b/x/')",
        ),
        # A trailing terminator is dropped.
        (
            "CREATE EXTERNAL TABLE s (a int) "
            "STORED AS PARQUET LOCATION 's3://b/x/';",
            "d",
            'CREATE TABLE "d"."s" ("a" int) '
            "WITH (format='PARQUET', external_location='s3://b/x/')",
        ),
        # Table and column COMMENTs pass through.
        (
            "CREATE EXTERNAL TABLE s (a int COMMENT 'the a') "
            "COMMENT 'table note' STORED AS PARQUET LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" int COMMENT \'the a\') '
            "COMMENT 'table note' WITH (format='PARQUET', "
            "external_location='s3://b/x/')",
        ),
        # CLUSTERED BY maps to bucketed_by + bucket_count.
        (
            "CREATE EXTERNAL TABLE s (a int, b string) "
            "CLUSTERED BY (a, b) INTO 8 BUCKETS "
            "STORED AS PARQUET LOCATION 's3://b/x/'",
            "d",
            'CREATE TABLE "d"."s" ("a" int, "b" varchar) '
            "WITH (format='PARQUET', external_location='s3://b/x/', "
            "bucketed_by=ARRAY['a','b'], bucket_count=8)",
        ),
        # ROW FORMAT DELIMITED separators map to textfile properties.
        (
            "CREATE EXTERNAL TABLE s (a string) "
            "ROW FORMAT DELIMITED FIELDS TERMINATED BY ',' "
            "ESCAPED BY '\\\\' NULL DEFINED AS 'null' "
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" varchar) '
            "WITH (format='TEXTFILE', external_location='s3://b/x/', "
            "textfile_field_separator=',', "
            "textfile_field_separator_escape='\\\\', "
            "null_format='null')",
        ),
        # The one TBLPROPERTY with a Trino equivalent.
        (
            "CREATE EXTERNAL TABLE s (a string) STORED AS TEXTFILE "
            "LOCATION 's3://b/x/' "
            "TBLPROPERTIES ('skip.header.line.count'='1', 'k'='v')",
            None,
            'CREATE TABLE "s" ("a" varchar) '
            "WITH (format='TEXTFILE', external_location='s3://b/x/', "
            "skip_header_line_count=1)",
        ),
        # No STORED AS: Hive/Athena default is TEXTFILE — Trino's own
        # default (ORC) would lie, so it is emitted explicitly.
        (
            "CREATE EXTERNAL TABLE s (a int) LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" int) '
            "WITH (format='TEXTFILE', external_location='s3://b/x/')",
        ),
        # SerDe disambiguates the TextInputFormat family.
        (
            "CREATE EXTERNAL TABLE s (a string) "
            "ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde' "
            "STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat' "
            "OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io."
            "HiveIgnoreKeyTextOutputFormat' LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" varchar) '
            "WITH (format='CSV', external_location='s3://b/x/')",
        ),
        (
            "CREATE EXTERNAL TABLE s (a string) "
            "ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe' "
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" varchar) '
            "WITH (format='OPENX_JSON', external_location='s3://b/x/')",
        ),
        (
            "CREATE EXTERNAL TABLE s (a string) "
            "ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.RegexSerDe' "
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" varchar) '
            "WITH (format='REGEX', external_location='s3://b/x/')",
        ),
        (
            "CREATE EXTERNAL TABLE s (a string) "
            "ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.lazy."
            "LazySimpleSerDe' STORED AS TEXTFILE LOCATION 's3://b/x/'",
            None,
            'CREATE TABLE "s" ("a" varchar) '
            "WITH (format='TEXTFILE', external_location='s3://b/x/')",
        ),
        # Escaped quotes in literals survive verbatim.
        (
            "CREATE EXTERNAL TABLE s (a int) "
            "STORED AS PARQUET LOCATION 's3://b/we''ird/'",
            None,
            'CREATE TABLE "s" ("a" int) '
            "WITH (format='PARQUET', external_location='s3://b/we''ird/')",
        ),
    ],
)
def test_external_table_mappings(
    query: str, database: str | None, expected: str
) -> None:
    assert to_trino_dialect(query, database) == expected


@pytest.mark.parametrize(
    "hive_type,trino_type",
    [
        ("string", "varchar"),
        ("float", "real"),
        ("binary", "varbinary"),
        ("int", "int"),
        ("bigint", "bigint"),
        ("double", "double"),
        ("boolean", "boolean"),
        ("date", "date"),
        ("timestamp", "timestamp"),
        ("decimal(10,2)", "decimal(10,2)"),
        ("varchar(20)", "varchar(20)"),
        ("char(5)", "char(5)"),
        ("array<string>", "array(varchar)"),
        ("map<string,int>", "map(varchar,int)"),
        ("struct<a:int,b:string>", 'row("a" int,"b" varchar)'),
        ("array<struct<k:string>>", 'array(row("k" varchar))'),
        ("map<string,array<int>>", "map(varchar,array(int))"),
    ],
)
def test_hive_column_types_translate(hive_type: str, trino_type: str) -> None:
    query = (
        f"CREATE EXTERNAL TABLE s (c {hive_type}) "
        "STORED AS PARQUET LOCATION 's3://b/x/'"
    )
    assert to_trino_dialect(query) == (
        f'CREATE TABLE "s" ("c" {trino_type}) '
        "WITH (format='PARQUET', external_location='s3://b/x/')"
    )


@pytest.mark.parametrize(
    "query",
    [
        # Not the Athena form at all — Trino handles it (or its own 400).
        "create table t (a integer)",
        "CREATE EXTERNAL TABLE t (a int) STORED AS PARQUET "
        "LOCATION 's3://b/x/'; DROP TABLE t",  # a second statement
        # Three-part names aren't Athena's grammar.
        "CREATE EXTERNAL TABLE catalog.db.t (a int) "
        "STORED AS PARQUET LOCATION 's3://b/x/'",
        # Unbalanced column list.
        "CREATE EXTERNAL TABLE t (a int STORED AS PARQUET "
        "LOCATION 's3://b/x/'",
        # Out-of-grammar clauses AWS itself rejects (Hive-only forms).
        "CREATE EXTERNAL TABLE t (a int) STORED BY 'handler.class' "
        "LOCATION 's3://b/x/'",
        "CREATE EXTERNAL TABLE t (a int) SKEWED BY (a) ON (1) "
        "STORED AS PARQUET LOCATION 's3://b/x/'",
        "CREATE EXTERNAL TABLE t (a int) CLUSTERED BY (a) "
        "SORTED BY (a) INTO 2 BUCKETS STORED AS PARQUET LOCATION 's3://b/'",
        "CREATE EXTERNAL TABLE t (a int) STORED AS DIRECTORIES "
        "LOCATION 's3://b/x/'",
        # INPUTFORMAT without its OUTPUTFORMAT pair is invalid on AWS too.
        "CREATE EXTERNAL TABLE t (a int) "
        "STORED AS INPUTFORMAT 'org.apache.hadoop.mapred.TextInputFormat' "
        "LOCATION 's3://b/x/'",
        # An unknown STORED AS name — invalid on AWS too.
        "CREATE EXTERNAL TABLE t (a int) STORED AS BOGUSFMT "
        "LOCATION 's3://b/x/'",
        # Keyword inside a literal — not statement-leading text.
        "SELECT 'CREATE EXTERNAL TABLE x (a int)'",
        # CREATE EXTERNAL VIEW, not a table.
        "CREATE EXTERNAL VIEW v AS SELECT 1",
    ],
)
def test_unmappable_or_non_athena_statements_pass_through(
    query: str,
) -> None:
    assert to_trino_dialect(query, "db") == query


@pytest.mark.parametrize(
    "query,offender",
    [
        # Valid Athena grammar the emulator cannot honor: the clause's
        # offending value is named in the submit-time 400 (UNLOAD posture).
        (
            "CREATE EXTERNAL TABLE t (a int) STORED AS PARQUET",
            "LOCATION",
        ),
        (
            "CREATE EXTERNAL TABLE t (a int) "
            "STORED AS INPUTFORMAT 'com.acme.WonkyInputFormat' "
            "OUTPUTFORMAT 'com.acme.WonkyOutputFormat' "
            "LOCATION 's3://b/x/'",
            "com.acme.WonkyInputFormat",
        ),
        (
            "CREATE EXTERNAL TABLE t (a int) "
            "ROW FORMAT SERDE 'com.acme.WonkySerDe' "
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            "com.acme.WonkySerDe",
        ),
        (
            "CREATE EXTERNAL TABLE t (a uniontype<int,string>) "
            "STORED AS PARQUET LOCATION 's3://b/x/'",
            "uniontype",
        ),
        (
            "CREATE EXTERNAL TABLE t (a string) ROW FORMAT DELIMITED "
            "LINES TERMINATED BY '\\n' "
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            "LINES TERMINATED BY",
        ),
        (
            "CREATE EXTERNAL TABLE t (a string) ROW FORMAT DELIMITED "
            "COLLECTION ITEMS TERMINATED BY '|' "
            "STORED AS TEXTFILE LOCATION 's3://b/x/'",
            "COLLECTION ITEMS TERMINATED BY",
        ),
        (
            "CREATE EXTERNAL TABLE t (a string) "
            "STORED AS TEXTFILE LOCATION 's3://b/x/' "
            "TBLPROPERTIES ('skip.header.line.count'='one')",
            "skip.header.line.count",
        ),
        # AWS's valid Amazon Ion storage format has no Trino counterpart.
        (
            "CREATE EXTERNAL TABLE t (a int) STORED AS ION "
            "LOCATION 's3://b/x/'",
            "ION",
        ),
        # A column-less table can't express a Trino column list.
        (
            "CREATE EXTERNAL TABLE t STORED AS PARQUET LOCATION 's3://b/x/'",
            "column",
        ),
    ],
)
def test_valid_athena_but_unmappable_raises_a_shaped_400(
    query: str, offender: str
) -> None:
    with pytest.raises(InvalidRequestException, match=offender):
        to_trino_dialect(query, "db")
