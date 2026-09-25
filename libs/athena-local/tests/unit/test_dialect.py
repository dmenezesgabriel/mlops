"""Unit tests for the Athena→Trino dialect map (``dialect.py``).

The CLI ``start-query-execution`` example runs
``create database if not exists newdb`` (valid Athena DDL — Athena's SQL
reference supports CREATE DATABASE), but Trino 483 rejects it (its Hive
connector vocabulary is ``CREATE SCHEMA``). The provider's exact lifecycle
spelling adds backtick identifiers and a terminal semicolon, which Trino also
rejects. Rewrites apply only to submitted statements; classification and
stored query text keep the original Athena SQL.
"""

from __future__ import annotations

import pytest
from athena_local.dialect import to_trino_dialect


def test_create_database_becomes_create_schema() -> None:
    assert (
        to_trino_dialect("create database if not exists newdb")
        == "create schema if not exists newdb"
    )


def test_provider_database_statements_use_trino_identifiers() -> None:
    assert to_trino_dialect("create database `analytics`;") == (
        'create schema "analytics"'
    )
    assert to_trino_dialect("drop database `analytics`;") == (
        'drop schema "analytics"'
    )


def test_uppercase_and_leading_whitespace_are_preserved() -> None:
    assert (
        to_trino_dialect("  CREATE DATABASE analytics")
        == "  CREATE SCHEMA analytics"
    )


@pytest.mark.parametrize(
    "query",
    [
        "select 1",
        "create table t (a integer)",
        "INSERT INTO x SELECT 'create database' FROM y",
    ],
)
def test_non_matching_statements_pass_through(query: str) -> None:
    assert to_trino_dialect(query) == query
