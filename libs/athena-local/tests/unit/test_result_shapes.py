"""Unit tests for Trino→Athena result shapes (``result_shapes.py``).

Trino's ``DESCRIBE`` answers ``Column | Type | Extra | Comment`` with
``Extra = 'partition key'`` marking partition columns, while Athena's wire
shape is ``col_name | data_type | comment`` with partition columns repeated
under ``# Partition Information``/``# col_name`` marker rows — the shape
wrangler's ``_parse_describe_table`` and ``show_create_table``
(``createtab_stmt``) read (awswrangler/athena/_utils.py:224-239, :1011).
"""

from __future__ import annotations

import pytest
from athena_local.result_shapes import to_athena_result_shape

TRINO_DESCRIBE_COLUMNS = [
    ("Column", "varchar"),
    ("Type", "varchar"),
    ("Extra", "varchar"),
    ("Comment", "varchar"),
]

ATHENA_DESCRIBE_COLUMNS = [
    ("col_name", "varchar"),
    ("data_type", "varchar"),
    ("comment", "varchar"),
]


def test_describe_columns_become_athena_shape() -> None:
    columns, rows = to_athena_result_shape(
        "DESCRIBE",
        TRINO_DESCRIBE_COLUMNS,
        [
            ["id", "bigint", "", ""],
            ["name", "varchar", "", "from deserializer"],
        ],
    )
    assert columns == ATHENA_DESCRIBE_COLUMNS
    assert rows == [
        ["id", "bigint", ""],
        ["name", "varchar", "from deserializer"],
    ]


def test_describe_partition_keys_repeat_under_markers() -> None:
    columns, rows = to_athena_result_shape(
        "DESCRIBE",
        TRINO_DESCRIBE_COLUMNS,
        [
            ["quantity", "bigint", "", ""],
            ["region", "varchar", "partition key", ""],
            ["amount", "decimal(10,2)", "partition key", ""],
        ],
    )
    assert columns == ATHENA_DESCRIBE_COLUMNS
    assert rows == [
        ["quantity", "bigint", ""],
        ["region", "varchar", ""],
        ["amount", "decimal(10,2)", ""],
        ["# Partition Information", "", ""],
        ["# col_name", "data_type", "comment"],
        ["region", "varchar", ""],
        ["amount", "decimal(10,2)", ""],
    ]


def test_describe_without_trino_signature_passes_through() -> None:
    columns = [("col_name", "varchar")]
    rows = [["x"]]
    assert to_athena_result_shape("DESCRIBE", columns, rows) == (columns, rows)


@pytest.mark.parametrize(
    "substatement_type", ["SHOW_CREATE_TABLE", "SHOW_CREATE_VIEW"]
)
def test_show_create_column_becomes_createtab_stmt(
    substatement_type: str,
) -> None:
    columns, rows = to_athena_result_shape(
        substatement_type,
        [("Create Table", "varchar")],
        [["CREATE TABLE hive.db.t (a integer)"]],
    )
    assert columns == [("createtab_stmt", "varchar")]
    assert rows == [["CREATE TABLE hive.db.t (a integer)"]]


def test_show_create_multi_column_passes_through() -> None:
    columns = [("a", "integer"), ("b", "varchar")]
    rows = [[1, "x"]]
    assert to_athena_result_shape("SHOW_CREATE_TABLE", columns, rows) == (
        columns,
        rows,
    )


@pytest.mark.parametrize("substatement_type", ["SELECT", None, "SHOW_TABLES"])
def test_other_substatements_pass_through(
    substatement_type: str | None,
) -> None:
    columns = [("a", "integer")]
    rows = [[1]]
    assert to_athena_result_shape(substatement_type, columns, rows) == (
        columns,
        rows,
    )
