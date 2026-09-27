"""Shared named fakes for Iceberg routing tests (ADR-0013).

``StaticIcebergProbe`` reports the (database, table) set it is seeded with
and records calls; ``route`` runs a statement through
``iceberg_trino_submission`` against it.
"""

from __future__ import annotations

from athena_local.iceberg import iceberg_trino_submission

DATABASE = "analytics"


class StaticIcebergProbe:
    """Named probe fake: reports the (database, table) set it is seeded with."""

    def __init__(self, iceberg_tables: set[tuple[str, str]]) -> None:
        self._iceberg_tables = iceberg_tables
        self.calls: list[tuple[str, str]] = []
        self.invalidations = 0

    def is_iceberg_table(self, database: str, table: str) -> bool:
        self.calls.append((database, table))
        return (database, table) in self._iceberg_tables

    def invalidate(self) -> None:
        self.invalidations += 1


def route(
    query: str,
    iceberg_tables: set[tuple[str, str]],
    database: str | None = DATABASE,
) -> str | None:
    return iceberg_trino_submission(
        query, database, StaticIcebergProbe(iceberg_tables)
    )
