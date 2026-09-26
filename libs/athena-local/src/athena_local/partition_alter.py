"""Athena ``ALTER TABLE … ADD PARTITION`` → Trino ``register_partition``.

Real Athena registers partitions with
``ALTER TABLE [db.]t ADD [IF NOT EXISTS] PARTITION (col='v' [, …])
[LOCATION 's3://…']`` (AWS docs ``alter-table-add-partition.html``). Trino
483's grammar has no ``ADD PARTITION`` form at all — the Hive connector
exposes registration through ``CALL system.register_partition(schema,
table, partition_columns, partition_values[, location])`` instead
(trino.io hive connector procedures), enabled by
``hive.allow-register-partition-procedure``.

An omitted ``LOCATION`` maps to the procedure's optional fifth argument —
Trino builds the default ``<table_location>/<col>=<v>/`` path, the same
default AWS documents. ``IF NOT EXISTS`` has no CALL equivalent: the
procedure raises ``ALREADY_EXISTS`` before mutating when the partition is
registered, so the flag rides the record and the executor treats that
error as the no-op AWS specifies. One Trino statement registers one
partition, so AWS-valid multi-``PARTITION`` adds are unrepresentable and
raise ``InvalidRequestException`` naming the limitation, while shapes real
Athena rejects pass through for Trino's own 400 — the same posture as
``external_table.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from athena_local.errors import InvalidRequestException
from athena_local.sql_lexing import (
    IDENTIFIER_PART,
    balanced_span,
    identifier_name,
    literal_value,
    split_target,
    split_top_level,
    sql_literal,
    string_end,
)

_HEAD = re.compile(r"(?i)^(?P<prefix>\s*)alter\s+table\b")
_TARGET = re.compile(
    rf"\s*(?P<target>(?:{IDENTIFIER_PART})"
    rf"(?:\s*\.\s*(?:{IDENTIFIER_PART}))*)"
)
_ADD = re.compile(r"(?i)\s+add\b")
_IF_NOT_EXISTS = re.compile(r"(?i)\s+if\s+not\s+exists\b")
_PARTITION = re.compile(r"(?i)\s+partition\s*\(")
_LOCATION = re.compile(r"(?i)\s+location\s*'")
_TAIL = re.compile(r"\s*;?\s*")

# One ``key = 'lit'`` (or bare-number) pair inside a PARTITION spec — the
# value forms AWS's DDL accepts; anything else stays for Trino to reject.
_SPEC_PAIR = re.compile(
    rf"^\s*(?P<key>{IDENTIFIER_PART})\s*=\s*"
    r"(?P<value>'(?:[^']|'')*'|[0-9]+(?:\.[0-9]+)?)\s*$"
)


@dataclass(frozen=True)
class AddPartitionCall:
    """The ``CALL system.register_partition`` an ADD PARTITION resolves to.

    ``noop_if_exists`` carries the statement's ``IF NOT EXISTS`` — the
    procedure's ``ALREADY_EXISTS`` fires only on a registered partition,
    before any mutation, which is exactly AWS's no-op; the executor
    succeeds the execution on that error instead of failing it.
    """

    sql: str
    noop_if_exists: bool


@dataclass
class _AddPartition:
    """The parsed pieces of ``ALTER TABLE t ADD PARTITION …``."""

    prefix: str
    schema: str | None = None
    table: str = ""
    if_not_exists: bool = False
    columns: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    location: str | None = None


def add_partition_trino_call(
    query: str, database: str | None
) -> AddPartitionCall | None:
    """The register_partition CALL an ADD PARTITION statement resolves to.

    Returns None — leaving the statement for Trino to handle — when it is
    not ``ALTER TABLE … ADD PARTITION`` (``ADD COLUMN`` and friends are
    Trino's own grammar), the spec is malformed, or the schema can't
    resolve (unqualified target with no ``database``). A second
    ``PARTITION`` clause raises ``InvalidRequestException``: AWS accepts
    multi-partition adds, but one Trino statement registers one partition.

    Example: ``ALTER TABLE db.t ADD PARTITION (r='AP') LOCATION 's3://x/'``
    emits ``CALL system.register_partition('db','t',ARRAY['r'],
    ARRAY['AP'],'s3://x/')``.
    """
    head = _HEAD.match(query)
    if head is None:
        return None
    parsed = _parse(query, head.end(), head.group("prefix"), database)
    if parsed is None:
        return None
    return _emit(parsed)


def _parse(
    query: str, cursor: int, prefix: str, database: str | None
) -> _AddPartition | None:
    acc = _AddPartition(prefix=prefix)
    target = _TARGET.match(query, cursor)
    if target is None:
        return None
    parts = [identifier_name(p) for p in split_target(target.group("target"))]
    if len(parts) > 2:
        return None
    acc.schema = parts[0] if len(parts) == 2 else database
    acc.table = parts[-1]
    if acc.schema is None:
        return None
    add = _ADD.match(query, target.end())
    if add is None:
        return None
    cursor = add.end()
    if_not_exists = _IF_NOT_EXISTS.match(query, cursor)
    if if_not_exists is not None:
        acc.if_not_exists = True
        cursor = if_not_exists.end()
    partition = _PARTITION.match(query, cursor)
    if partition is None:
        return None
    end = _partition_spec(query, partition.end() - 1, acc)
    if end is None:
        return None
    return _partition_tail(query, end, acc)


def _partition_spec(query: str, paren: int, acc: _AddPartition) -> int | None:
    """``(col='v', …)`` at ``paren`` → cursor past ``)``; None if not one."""
    end = balanced_span(query, paren)
    if end is None:
        return None
    pairs = split_top_level(query[paren + 1 : end - 1])
    for pair in pairs:
        match = _SPEC_PAIR.match(pair)
        if match is None:
            return None
        value = _spec_value(match.group("value"))
        if value is None:
            return None
        acc.columns.append(identifier_name(match.group("key")))
        acc.values.append(value)
    return end


def _spec_value(raw: str) -> str | None:
    """The partition value: ``'lit'`` unescaped, a bare number verbatim."""
    if raw.startswith("'"):
        return literal_value(raw)
    return raw


def _partition_tail(
    query: str, cursor: int, acc: _AddPartition
) -> _AddPartition | None:
    """Optional ``LOCATION 'lit'``, then the statement tail or a rejection."""
    location = _LOCATION.match(query, cursor)
    if location is not None:
        end = string_end(query, location.end() - 1)
        if end is None:
            return None
        acc.location = literal_value(query[location.end() - 1 : end])
        cursor = end
    if _PARTITION.match(query, cursor) is not None:
        raise InvalidRequestException(
            "ALTER TABLE … ADD with multiple PARTITION clauses is not "
            "supported; expected one PARTITION (col='v', …) per statement"
        )
    if _TAIL.fullmatch(query[cursor:]) is None:
        return None
    return acc


def _emit(acc: _AddPartition) -> AddPartitionCall:
    """The 4- or 5-argument ``register_partition`` CALL (LOCATION optional)."""
    assert acc.schema is not None  # _parse guarantees resolution
    columns = ",".join(f"'{sql_literal(c)}'" for c in acc.columns)
    values = ",".join(f"'{sql_literal(v)}'" for v in acc.values)
    args = (
        f"'{sql_literal(acc.schema)}','{sql_literal(acc.table)}',"
        f"ARRAY[{columns}],ARRAY[{values}]"
    )
    if acc.location is not None:
        args += f",'{sql_literal(acc.location)}'"
    return AddPartitionCall(
        sql=f"{acc.prefix}CALL system.register_partition({args})",
        noop_if_exists=acc.if_not_exists,
    )
