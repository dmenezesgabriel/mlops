"""Trino utility-statement results translated to Athena's wire shape.

The engine's ``DESCRIBE`` answers ``Column | Type | Extra | Comment`` with
``Extra = 'partition key'`` on partition columns, while Athena's result set
is ``col_name | data_type | comment`` and repeats partition columns under
``# Partition Information``/``# col_name`` marker rows — the shape
awswrangler's ``_parse_describe_table`` consumes
(awswrangler/athena/_utils.py:224-239). Trino's ``SHOW CREATE TABLE``
single ``Create Table`` column is Athena's ``createtab_stmt``
(_utils.py:1011). The executor reshapes at the cache boundary so
``GetQueryResults`` ColumnInfo and the ``.txt`` artifact carry the same
names consumers parse.

Type spellings stay Trino's (``varchar`` where Athena would say ``string``);
the parsed contracts only depend on column names and row layout.
"""

from __future__ import annotations

_TRINO_DESCRIBE_COLUMNS = ["Column", "Type", "Extra", "Comment"]
_ATHENA_DESCRIBE_COLUMNS = [
    ("col_name", "varchar"),
    ("data_type", "varchar"),
    ("comment", "varchar"),
]
_ATHENA_SHOW_CREATE_COLUMN = ("createtab_stmt", "varchar")
_SHOW_CREATE_SUBSTATEMENTS = {"SHOW_CREATE_TABLE", "SHOW_CREATE_VIEW"}


def to_athena_result_shape(
    substatement_type: str | None,
    columns: list[tuple[str, str]],
    rows: list[list[object]],
) -> tuple[list[tuple[str, str]], list[list[object]]]:
    """Translate an engine result to the Athena wire shape, when one exists.

    DESCRIBE maps only when the page carries Trino's exact four-column
    signature — anything else (already-Athena shape, engine drift) passes
    through untouched rather than mangle unknown layouts.
    """
    if substatement_type == "DESCRIBE":
        return _describe_shape(columns, rows)
    if substatement_type in _SHOW_CREATE_SUBSTATEMENTS:
        return _show_create_shape(columns, rows)
    return columns, rows


def _describe_shape(
    columns: list[tuple[str, str]], rows: list[list[object]]
) -> tuple[list[tuple[str, str]], list[list[object]]]:
    if [name for name, _type in columns] != _TRINO_DESCRIBE_COLUMNS:
        return columns, rows
    plain: list[list[object]] = []
    partitioned: list[list[object]] = []
    for row in rows:
        entry = [row[0], row[1], row[3]]
        plain.append(entry)
        if str(row[2]).lower() == "partition key":
            partitioned.append(entry)
    if not partitioned:
        return list(_ATHENA_DESCRIBE_COLUMNS), plain
    return list(_ATHENA_DESCRIBE_COLUMNS), [
        *plain,
        ["# Partition Information", "", ""],
        ["# col_name", "data_type", "comment"],
        *partitioned,
    ]


def _show_create_shape(
    columns: list[tuple[str, str]], rows: list[list[object]]
) -> tuple[list[tuple[str, str]], list[list[object]]]:
    if len(columns) != 1:
        return columns, rows
    return [_ATHENA_SHOW_CREATE_COLUMN], rows
