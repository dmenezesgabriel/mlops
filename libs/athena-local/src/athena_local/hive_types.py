"""Hive column type and column-definition spellings → Trino spellings.

Athena DDL carries Hive types (``string``, ``float``, ``binary``,
``struct<…>``, ``array<…>``, ``map<…>``) that Trino 483 either renames
(``varchar``/``real``/``varbinary``) or spells differently
(``row(…)``/``array(…)``/``map(…)`` — probed: the bare Hive names are
unknown types on the coordinator). ``uniontype`` is valid Hive with no
Trino counterpart and raises ``InvalidRequestException``; text that is not
a parseable type returns None so the caller can pass the statement through
for the engine's own rejection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from athena_local.errors import InvalidRequestException
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    balanced_span,
    identifier_name,
    quoted_identifier,
    string_end,
)

_TYPE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_TYPE_SCALARS = {
    "tinyint",
    "smallint",
    "int",
    "integer",
    "bigint",
    "double",
    "real",
    "boolean",
    "date",
    "timestamp",
    "decimal",
    "varchar",
    "char",
    "varbinary",
    "string",
    "float",
    "binary",
}
_TYPE_RENAMES = {"string": "varchar", "float": "real", "binary": "varbinary"}

_COLUMN_DEF = re.compile(
    rf"(?is)^\s*(?P<name>{IDENTIFIER_PART})\s+(?P<rest>.+?)\s*$"
)
_COLUMN_COMMENT = re.compile(r"(?is)\s+comment\s+('(?:[^']|'')*')\s*$")
_STRUCT_FIELD = re.compile(rf"\s*(?P<name>{IDENTIFIER_PART})\s*:")


@dataclass
class HiveColumn:
    """A column def folded to its emitted form plus its folded name."""

    name: str  # unquoted/folded, for partitioned_by/bucketed_by arrays
    sql: str  # emitted ``"name" type [COMMENT 'x']`` fragment


def hive_type_to_trino(text: str) -> str | None:
    """The Trino spelling of a Hive type; None when unparseable."""
    parsed = _parse_type(text, 0)
    if parsed is None:
        return None
    trino_type, index = parsed
    if text[index:].strip():
        return None
    return trino_type


def _split_defs(text: str) -> list[str]:
    """Comma-split a column list, honoring ``<…>``/``(…)`` nesting."""
    parts: list[str] = []
    depth, start, cursor = 0, 0, 0
    while cursor < len(text):
        char = text[cursor]
        if char in "(<":
            depth += 1
        elif char in ")>":
            depth -= 1
        elif char == "'":
            end = string_end(text, cursor)
            cursor = end if end is not None else len(text)
            continue
        elif char == "," and depth == 0:
            parts.append(text[start:cursor])
            start = cursor + 1
        cursor += 1
    parts.append(text[start:])
    return parts


def hive_column_defs(text: str) -> list[HiveColumn] | None:
    """``name type [COMMENT 'x']`` defs → emitted fragments; None on bad input."""
    columns: list[HiveColumn] = []
    for raw in _split_defs(text):
        match = _COLUMN_DEF.match(raw)
        if match is None:
            return None
        rest = match.group("rest")
        comment = _COLUMN_COMMENT.search(rest)
        suffix = ""
        if comment is not None:
            suffix = f" COMMENT {comment.group(1)}"
            rest = rest[: comment.start()]
        trino_type = hive_type_to_trino(rest)
        if trino_type is None:
            return None
        name = identifier_name(match.group("name"))
        sql = f'"{quoted_identifier(name)}" {trino_type}{suffix}'
        columns.append(HiveColumn(name=name, sql=sql))
    return columns


def _parse_type(text: str, index: int) -> tuple[str, int] | None:
    index = _skip_ws(text, index)
    match = _TYPE_NAME.match(text, index)
    if match is None:
        return None
    name = match.group(0).lower()
    index = match.end()
    if name == "uniontype":
        raise InvalidRequestException(
            "column type 'uniontype' is not supported; Trino has no union type"
        )
    if name in ("array", "map", "struct"):
        return _complex_type(text, index, name)
    if name not in _TYPE_SCALARS:
        return None
    params = _skip_ws(text, index)
    if params < len(text) and text[params] == "(":
        end = balanced_span(text, params)
        if end is None:
            return None
        return f"{name}{text[params:end]}", end
    return _TYPE_RENAMES.get(name, name), index


def _complex_type(text: str, index: int, name: str) -> tuple[str, int] | None:
    open_angle = _expect(text, index, "<")
    if open_angle is None:
        return None
    if name == "struct":
        return _struct_type(text, open_angle)
    inner = _type_list(text, open_angle, 1 if name == "array" else 2)
    if inner is None:
        return None
    types, index = inner
    return f"{name}({','.join(types)})", index


def _type_list(
    text: str, index: int, count: int
) -> tuple[list[str], int] | None:
    types: list[str] = []
    while True:
        parsed = _parse_type(text, index)
        if parsed is None:
            return None
        types.append(parsed[0])
        delimiter = _expect(
            text, parsed[1], "," if len(types) < count else ">"
        )
        if delimiter is None:
            return None
        index = delimiter
        if len(types) == count:
            return types, index


def _struct_type(text: str, index: int) -> tuple[str, int] | None:
    fields: list[str] = []
    while True:
        field = _struct_field(text, index)
        if field is None:
            return None
        field_type = _parse_type(text, field[1])
        if field_type is None:
            return None
        fields.append(f'"{quoted_identifier(field[0])}" {field_type[0]}')
        close = _expect(text, field_type[1], ">")
        if close is not None:
            return f"row({','.join(fields)})", close
        delimiter = _expect(text, field_type[1], ",")
        if delimiter is None:
            return None
        index = delimiter


def _struct_field(text: str, index: int) -> tuple[str, int] | None:
    match = _STRUCT_FIELD.match(text, index)
    if match is None:
        return None
    return identifier_name(match.group("name")), match.end()


def _expect(text: str, index: int, char: str) -> int | None:
    index = _skip_ws(text, index)
    if index < len(text) and text[index] == char:
        return index + 1
    return None


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\n\r":
        index += 1
    return index
