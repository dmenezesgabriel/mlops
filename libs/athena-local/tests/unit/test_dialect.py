"""Unit tests for the Athena→Trino dialect map (``dialect.py``).

CS-3 surfaced the map's first entry: the CLI's ``start-query-execution``
example 2 runs ``create database if not exists newdb`` (valid Athena DDL —
Athena's SQL reference supports CREATE DATABASE), but Trino 483 rejects it
(``mismatched input 'database'``; Trino's hive connector vocabulary is
``CREATE SCHEMA``, which maps to the Glue metastore database). The rewrite
applies only to the submitted statement; classification and the stored
query text keep the original Athena SQL.
"""

from __future__ import annotations

import pytest
from athena_local.dialect import to_trino_dialect


def test_create_database_becomes_create_schema() -> None:
    assert (
        to_trino_dialect("create database if not exists newdb")
        == "create schema if not exists newdb"
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
        "drop database analytics",
        "INSERT INTO x SELECT 'create database' FROM y",
    ],
)
def test_non_matching_statements_pass_through(query: str) -> None:
    assert to_trino_dialect(query) == query
