"""Athena ``CREATE EXTERNAL TABLE`` → Trino ``CREATE TABLE … WITH(…)``.

Real Athena accepts Hive-style external-table DDL (AWS docs,
``athena/latest/ug/create-table.html``) — the exact spelling awswrangler's
``generate_create_query`` emits (``awswrangler/athena/_utils.py:1076``).
Trino 483's grammar has no ``EXTERNAL`` form, so the statement is rewritten
to ``CREATE TABLE … WITH (format, external_location, partitioned_by[, …])``.

Only statement-leading statements map, and only the AWS-documented clause
set: shapes real Athena rejects pass through for Trino's own 400, while
AWS-valid but unrepresentable input raises ``InvalidRequestException``,
naming the offender. ``TBLPROPERTIES``/``SERDEPROPERTIES`` beyond
``skip.header.line.count`` are dropped — the documented limitation.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from athena_local.errors import InvalidRequestException
from athena_local.hive_types import HiveColumn, hive_column_defs
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    balanced_span,
    identifier_name,
    literal_value,
    quoted_identifier,
    split_target,
    split_top_level,
    sql_literal,
    string_end,
)

_HEAD = re.compile(r"(?i)^(?P<prefix>\s*)create\s+external\s+table\b")
_IF_NOT_EXISTS = re.compile(r"(?i)\s*if\s+not\s+exists\b")
_TARGET = re.compile(
    rf"\s*(?P<target>(?:{IDENTIFIER_PART})"
    rf"(?:\s*\.\s*(?:{IDENTIFIER_PART}))*)"
)
_TAIL_END = re.compile(r"\s*;?\s*")
_CLAUSE_WORD = re.compile(r"(?i)\s*([A-Za-z_]+)")
_IDENTIFIER = re.compile(IDENTIFIER_PART)

# INPUTFORMAT class → Trino storage format name (trino-483 HiveStorageFormat).
_INPUT_FORMAT_CLASSES = {
    "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat": "PARQUET",
    "org.apache.hadoop.hive.ql.io.orc.OrcInputFormat": "ORC",
    "org.apache.hadoop.hive.ql.io.avro.AvroContainerInputFormat": "AVRO",
    "org.apache.hadoop.hive.ql.io.HiveSequenceFileInputFormat": "SEQUENCEFILE",
    "org.apache.hadoop.mapred.SequenceFileInputFormat": "SEQUENCEFILE",
    "org.apache.hadoop.hive.ql.io.RCFileInputFormat": "RCTEXT",
    "org.apache.hadoop.mapred.TextInputFormat": "TEXTFILE",
}

# SerDe → Trino format, consulted only when the format resolved to the
# TEXTFILE family — the serde picks the actual text reader.
_SERDE_FORMATS = {
    "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe": "TEXTFILE",
    "org.apache.hadoop.hive.serde2.lazybinary.LazyBinarySerDe": "TEXTFILE",
    "org.apache.hadoop.hive.serde2.OpenCSVSerde": "CSV",
    "org.openx.data.jsonserde.JsonSerDe": "OPENX_JSON",
    "org.apache.hadoop.hive.serde2.JsonSerDe": "JSON",
    "org.apache.hadoop.hive.serde2.RegexSerDe": "REGEX",
}

# Athena's ``STORED AS <name>`` spellings → Trino format. ``RCFILE`` is the
# columnar-text RCFile pair; ``ION`` is AWS-valid but has no Trino format.
_STORED_AS_FORMATS = {
    "parquet": "PARQUET",
    "orc": "ORC",
    "avro": "AVRO",
    "csv": "CSV",
    "textfile": "TEXTFILE",
    "json": "JSON",
    "openx_json": "OPENX_JSON",
    "sequencefile": "SEQUENCEFILE",
    "regex": "REGEX",
    "rcbinary": "RCBINARY",
    "rctext": "RCTEXT",
    "rcfile": "RCTEXT",
}


# Text-family formats where the row-level props carry meaning.
_TEXT_FORMATS = {"TEXTFILE", "CSV", "JSON", "OPENX_JSON", "REGEX"}


@dataclass
class _ExternalTable:
    """The parsed pieces of a CREATE EXTERNAL TABLE statement."""

    prefix: str
    if_not_exists: bool = False
    schema: str | None = None
    table: str = ""
    columns: list[HiveColumn] = field(default_factory=list)
    partition_columns: list[HiveColumn] = field(default_factory=list)
    table_comment: str | None = None  # raw ``'lit'`` literals below
    format_name: str | None = None
    input_format: str | None = None
    serde: str | None = None
    field_separator: str | None = None
    field_separator_escape: str | None = None
    null_format: str | None = None
    location: str | None = None
    bucketed_by: list[str] = field(default_factory=list)
    bucket_count: str | None = None
    skip_header_line_count: int | None = None


def external_table_trino_ddl(query: str, database: str | None) -> str | None:
    """The Trino ``CREATE TABLE … WITH(…)`` this statement maps to.

    None unless it leads with ``CREATE EXTERNAL TABLE`` in the
    AWS-documented shape; ``InvalidRequestException`` names AWS-valid
    input the emulator cannot honor.
    """
    head = _HEAD.match(query)
    if head is None:
        return None
    parsed = _parse(query, head.end(), head.group("prefix"))
    if parsed is None:
        return None
    return _emit(parsed, database)


def _parse(query: str, cursor: int, prefix: str) -> _ExternalTable | None:
    acc = _ExternalTable(prefix=prefix)
    end = _parse_head(query, cursor, acc)
    if end is None:
        return None
    while _TAIL_END.fullmatch(query[end:]) is None:
        matched = _match_clause(query, end, acc)
        if matched is None:
            return None
        end = matched
    return _check_required(acc)


def _parse_head(query: str, cursor: int, acc: _ExternalTable) -> int | None:
    """``[IF NOT EXISTS] [db.]table [(cols)]`` → cursor past it, or None."""
    if_not_exists = _IF_NOT_EXISTS.match(query, cursor)
    if if_not_exists is not None:
        acc.if_not_exists = True
        cursor = if_not_exists.end()
    target = _TARGET.match(query, cursor)
    if target is None:
        return None
    parts = [identifier_name(p) for p in split_target(target.group("target"))]
    if len(parts) > 2:
        return None
    acc.schema = parts[0] if len(parts) == 2 else None
    acc.table = parts[-1]
    cursor = _skip_ws(query, target.end())
    if cursor < len(query) and query[cursor] == "(":
        return _column_list(query, cursor, acc)
    return cursor


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\n\r":
        index += 1
    return index


def _column_list(query: str, cursor: int, acc: _ExternalTable) -> int | None:
    end = balanced_span(query, cursor)
    if end is None:
        return None
    columns = hive_column_defs(query[cursor + 1 : end - 1])
    if columns is None:
        return None
    acc.columns = columns
    return end


def _check_required(acc: _ExternalTable) -> _ExternalTable:
    if acc.location is None:
        raise InvalidRequestException(
            "CREATE EXTERNAL TABLE without LOCATION is not supported; "
            "expected LOCATION 's3://…'"
        )
    if not acc.columns and not acc.partition_columns:
        raise InvalidRequestException(
            "CREATE EXTERNAL TABLE with no columns is not supported; "
            "expected a (col_name data_type, …) column list"
        )
    return acc


def _match_clause(query: str, cursor: int, acc: _ExternalTable) -> int | None:
    word = _CLAUSE_WORD.match(query, cursor)
    if word is None:
        return None
    matcher = _CLAUSE_MATCHERS.get(word.group(1).lower())
    if matcher is None:
        return None
    return matcher(query, cursor, acc)


_TABLE_COMMENT = re.compile(r"(?i)\s*comment\s*'")
_PARTITIONED_BY = re.compile(r"(?i)\s*partitioned\s+by\s*\(")
_CLUSTERED_BY = re.compile(r"(?i)\s*clustered\s+by\s*\(")
_INTO_BUCKETS = re.compile(r"(?i)\s*into\s+(\d+)\s+buckets\b")
_ROW_FORMAT = re.compile(r"(?i)\s*row\s+format\b")
_SERDE = re.compile(r"(?i)\s*serde\s*'")
_SERDEPROPERTIES = re.compile(r"(?i)\s*with\s+serdeproperties\s*\(")
_DELIMITED = re.compile(r"(?i)\s*delimited\b")
_STORED_AS = re.compile(r"(?i)\s*stored\s+as\b")
_INPUTFORMAT = re.compile(r"(?i)\s*inputformat\s*'")
_OUTPUTFORMAT = re.compile(r"(?i)\s*outputformat\s*'")
_LOCATION = re.compile(r"(?i)\s*location\s*'")
_TBLPROPERTIES = re.compile(r"(?i)\s*tblproperties\s*\(")
_TBLPROP_PAIR = re.compile(r"^\s*'((?:[^']|'')*)'\s*=\s*'((?:[^']|'')*)'\s*$")


def _raw_literal(query: str, match: re.Match[str]) -> tuple[str, int] | None:
    """The ``'lit'`` starting at ``match.end() - 1`` → (raw, end)."""
    end = string_end(query, match.end() - 1)
    if end is None:
        return None
    return query[match.end() - 1 : end], end


def _match_partitioned_by(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    match = _PARTITIONED_BY.match(query, cursor)
    if match is None:
        return None
    end = balanced_span(query, match.end() - 1)
    if end is None:
        return None
    columns = hive_column_defs(query[match.end() : end - 1])
    if columns is None:
        return None
    acc.partition_columns = columns
    return end


def _match_clustered_by(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    match = _CLUSTERED_BY.match(query, cursor)
    if match is None:
        return None
    end = balanced_span(query, match.end() - 1)
    if end is None:
        return None
    parts = [p.strip() for p in split_top_level(query[match.end() : end - 1])]
    if not parts or not all(_IDENTIFIER.fullmatch(p) for p in parts):
        return None
    # SORTED BY / missing INTO n BUCKETS aren't AWS-valid — pass through.
    buckets = _INTO_BUCKETS.match(query, end)
    if buckets is None:
        return None
    acc.bucketed_by = [identifier_name(p) for p in parts]
    acc.bucket_count = buckets.group(1)
    return buckets.end()


def _match_row_format(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    match = _ROW_FORMAT.match(query, cursor)
    if match is None:
        return None
    serde = _SERDE.match(query, match.end())
    if serde is None:
        delimited = _DELIMITED.match(query, match.end())
        if delimited is None:
            return None
        return _delimited_clauses(query, delimited.end(), acc)
    literal = _raw_literal(query, serde)
    if literal is None:
        return None
    raw, pos = literal
    acc.serde = literal_value(raw)
    props = _SERDEPROPERTIES.match(query, pos)
    if props is None:
        return pos
    # SERDEPROPERTIES are parsed and dropped — documented limitation.
    return balanced_span(query, props.end() - 1)


# Each supported sub-clause's named group IS the dataclass attribute it sets.
_DELIMITED_CLAUSE = re.compile(
    r"(?i)\s*(?:(?P<unsupported>collection\s+items|map\s+keys|lines)"
    r"\s+terminated\s+by"
    r"|fields\s+terminated\s+by(?P<field_separator>\s*')"
    r"|escaped\s+by(?P<field_separator_escape>\s*')"
    r"|null\s+defined\s+as(?P<null_format>\s*'))"
)


def _delimited_clauses(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    while True:
        match = _DELIMITED_CLAUSE.match(query, cursor)
        if match is None:
            return cursor
        if match.group("unsupported") is not None:
            clause = match.group("unsupported").upper()
            raise InvalidRequestException(
                f"ROW FORMAT DELIMITED {clause} TERMINATED BY is not "
                "supported; Trino has no equivalent table property"
            )
        literal = _raw_literal(query, match)
        if literal is None:
            return None
        raw, cursor = literal
        setattr(acc, match.lastgroup or "", raw)


def _match_stored_as(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    match = _STORED_AS.match(query, cursor)
    if match is None:
        return None
    pos = match.end()
    input_format = _INPUTFORMAT.match(query, pos)
    if input_format is not None:
        return _input_output_formats(query, input_format, acc)
    word = _CLAUSE_WORD.match(query, pos)
    if word is None:
        return None
    name = word.group(1).lower()
    if name == "ion":
        raise InvalidRequestException(
            "STORED AS 'ION' is not supported; Trino has no Ion format"
        )
    if name not in _STORED_AS_FORMATS:
        return None  # AWS rejects the name itself — pass through.
    acc.format_name = _STORED_AS_FORMATS[name]
    return word.end()


def _input_output_formats(
    query: str, match: re.Match[str], acc: _ExternalTable
) -> int | None:
    in_literal = _raw_literal(query, match)
    if in_literal is None:
        return None
    in_raw, pos = in_literal
    output_format = _OUTPUTFORMAT.match(query, pos)
    if output_format is None:
        return None  # INPUTFORMAT without its pair — invalid on AWS too.
    out_literal = _raw_literal(query, output_format)
    if out_literal is None:
        return None
    acc.input_format = literal_value(in_raw)
    return out_literal[1]


def _literal_matcher(
    pattern: re.Pattern[str], attribute: str
) -> Callable[[str, int, _ExternalTable], int | None]:
    """A clause matcher for ``KEYWORD 'lit'`` shapes (COMMENT, LOCATION)."""

    def match(query: str, cursor: int, acc: _ExternalTable) -> int | None:
        matched = pattern.match(query, cursor)
        if matched is None:
            return None
        literal = _raw_literal(query, matched)
        if literal is None:
            return None
        setattr(acc, attribute, literal[0])
        return literal[1]

    return match


def _match_serde_properties(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    match = _SERDEPROPERTIES.match(query, cursor)
    if match is None:
        return None
    # Top-level WITH SERDEPROPERTIES — dropped, same limitation.
    return balanced_span(query, match.end() - 1)


def _match_tblproperties(
    query: str, cursor: int, acc: _ExternalTable
) -> int | None:
    match = _TBLPROPERTIES.match(query, cursor)
    if match is None:
        return None
    end = balanced_span(query, match.end() - 1)
    if end is None:
        return None
    for pair in split_top_level(query[match.end() : end - 1]):
        if not pair.strip():
            continue
        kv = _TBLPROP_PAIR.match(pair)
        if kv is None:
            return None
        key = kv.group(1).replace("''", "'")
        if key.lower() != "skip.header.line.count":
            continue  # Others are dropped — documented limitation.
        value = kv.group(2).replace("''", "'")
        if not value.isdigit():
            raise InvalidRequestException(
                f"TBLPROPERTIES 'skip.header.line.count' value {value!r} "
                "is not supported; expected a non-negative integer"
            )
        acc.skip_header_line_count = int(value)
    return end


def _resolve_format(acc: _ExternalTable) -> str:
    file_format = acc.format_name
    if file_format is None and acc.input_format is not None:
        file_format = _INPUT_FORMAT_CLASSES.get(acc.input_format)
        if file_format is None:
            raise InvalidRequestException(
                f"INPUTFORMAT class {acc.input_format!r} is not supported; "
                f"expected one of {sorted(_INPUT_FORMAT_CLASSES)}"
            )
    if file_format != "TEXTFILE":
        return file_format or "TEXTFILE"
    if acc.serde is None:
        return "TEXTFILE"
    serde_format = _SERDE_FORMATS.get(acc.serde)
    if serde_format is None:
        raise InvalidRequestException(
            f"SERDE {acc.serde!r} is not supported; expected one of "
            f"{sorted(_SERDE_FORMATS)}"
        )
    return serde_format


def _with_properties(acc: _ExternalTable) -> list[str]:
    file_format = _resolve_format(acc)
    properties = [
        f"format='{file_format}'",
        f"external_location={acc.location}",
    ]
    if acc.partition_columns:
        names = ",".join(
            f"'{sql_literal(c.name)}'" for c in acc.partition_columns
        )
        properties.append(f"partitioned_by=ARRAY[{names}]")
    if acc.bucketed_by:
        names = ",".join(f"'{sql_literal(n)}'" for n in acc.bucketed_by)
        properties.append(f"bucketed_by=ARRAY[{names}]")
        properties.append(f"bucket_count={acc.bucket_count}")
    if file_format == "TEXTFILE":
        _textfile_properties(acc, properties)
    # skip_header_line_count carries meaning only for text-family formats.
    if acc.skip_header_line_count is not None and file_format in _TEXT_FORMATS:
        properties.append(
            f"skip_header_line_count={acc.skip_header_line_count}"
        )
    return properties


def _textfile_properties(acc: _ExternalTable, properties: list[str]) -> None:
    if acc.field_separator is not None:
        properties.append(f"textfile_field_separator={acc.field_separator}")
    if acc.field_separator_escape is not None:
        properties.append(
            f"textfile_field_separator_escape={acc.field_separator_escape}"
        )
    if acc.null_format is not None:
        properties.append(f"null_format={acc.null_format}")


def _emit(acc: _ExternalTable, database: str | None) -> str:
    name = f'"{quoted_identifier(acc.table)}"'
    if acc.schema is not None:
        name = f'"{quoted_identifier(acc.schema)}".{name}'
    elif database is not None:
        name = f'"{quoted_identifier(database)}".{name}'
    if_not_exists = "IF NOT EXISTS " if acc.if_not_exists else ""
    columns = ", ".join(c.sql for c in [*acc.columns, *acc.partition_columns])
    comment = f" COMMENT {acc.table_comment}" if acc.table_comment else ""
    return (
        f"{acc.prefix}CREATE TABLE {if_not_exists}{name} ({columns})"
        f"{comment} WITH ({', '.join(_with_properties(acc))})"
    )


_CLAUSE_MATCHERS: dict[
    str, Callable[[str, int, _ExternalTable], int | None]
] = {
    "comment": _literal_matcher(_TABLE_COMMENT, "table_comment"),
    "partitioned": _match_partitioned_by,
    "clustered": _match_clustered_by,
    "row": _match_row_format,
    "stored": _match_stored_as,
    "with": _match_serde_properties,
    "location": _literal_matcher(_LOCATION, "location"),
    "tblproperties": _match_tblproperties,
}
