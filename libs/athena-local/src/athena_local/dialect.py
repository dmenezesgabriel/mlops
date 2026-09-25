"""Athena-to-Trino statement dialect map (CS-3 evidence, gated).

Real Athena parses a slightly wider SQL vocabulary than the Trino 483
engine underneath this emulator. When a document statement is valid Athena
but unparseable by Trino, the ``to_trino_dialect`` prefix rewrite maps it to
Trino's equivalent before submit; classification and the stored
``QueryExecution.Query`` keep the original Athena text (matching real
Athena, which reports the query as written).

Currently mapped (each entry added only with evidence):

* ``CREATE DATABASE …`` → ``CREATE SCHEMA …`` — Athena's SQL reference
  documents CREATE DATABASE (a Glue metastore database); Trino rejects the
  keyword and its hive connector creates the metastore database via
  ``CREATE SCHEMA``. Surfaced by the awscli ``start-query-execution``
  example 2 (``create database if not exists newdb``) in CS-3.
"""

from __future__ import annotations

import re

# Anchored at the statement start so a ``create database`` phrase inside a
# SELECT or string literal is never rewritten; case-insensitive so athena
# style case survives and the replacement mirrors the original keyword's case.
_CREATE_DATABASE_PREFIX = re.compile(r"(?i)^(\s*create\s+)(database)\b")


def _schema_replacement(match: re.Match[str]) -> str:
    prefix, keyword = match.group(1), match.group(2)
    replacement = "SCHEMA" if keyword.isupper() else "schema"
    return f"{prefix}{replacement}"


def to_trino_dialect(query: str) -> str:
    """Map Athena statement keywords Trino cannot parse to their equivalents.

    ``create database if not exists newdb`` is submitted as
    ``create schema if not exists newdb`` (and ``CREATE DATABASE`` as
    ``CREATE SCHEMA``); every other statement — and every non-prefix
    ``create database`` occurrence — passes through unchanged.
    """
    return _CREATE_DATABASE_PREFIX.sub(_schema_replacement, query, count=1)
