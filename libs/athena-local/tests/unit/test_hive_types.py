"""Unit tests for the Hive type parser's nesting guard.

Trino's parser reports a stack overflow while parsing as a parse error
("is too large (stack overflow while parsing)"), never an internal failure;
the emulator mirrors that: a Hive type nesting past the recursive-descent
parser's safe bound raises a shaped ``InvalidRequestException`` instead of
leaking ``RecursionError`` into an ``InternalServerException``.
"""

from __future__ import annotations

import pytest
from athena_local.dialect import to_trino_dialect
from athena_local.errors import InvalidRequestException
from athena_local.hive_types import _MAX_TYPE_NESTING, hive_type_to_trino


def _nested_array(depth: int) -> str:
    """``array<`` x depth wrapping ``int``, closed with matching ``>``s."""
    return "array<" * depth + "int" + ">" * depth


def test_type_at_the_nesting_bound_still_maps() -> None:
    assert hive_type_to_trino(_nested_array(_MAX_TYPE_NESTING)) == (
        "array(" * _MAX_TYPE_NESTING + "int" + ")" * _MAX_TYPE_NESTING
    )


def test_type_past_the_nesting_bound_raises_a_shaped_400() -> None:
    with pytest.raises(
        InvalidRequestException,
        match=f"depth {_MAX_TYPE_NESTING + 1} exceeds the supported "
        f"maximum {_MAX_TYPE_NESTING}",
    ):
        hive_type_to_trino(_nested_array(_MAX_TYPE_NESTING + 1))


def test_deep_external_table_column_raises_a_shaped_400() -> None:
    """The AU-22 P-2 bisection boundary (331 nested ``array<``) → 400."""
    query = (
        f"CREATE EXTERNAL TABLE t (a {_nested_array(331)}) "
        "STORED AS PARQUET LOCATION 's3://b/x/'"
    )
    with pytest.raises(InvalidRequestException, match="nesting depth"):
        to_trino_dialect(query, "db")
