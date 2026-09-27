"""Iceberg verdict probe over Glue, with a cross-statement cache.

``iceberg.py`` routes statements to the dedicated ``iceberg`` Trino catalog
based on each referenced table's Glue ``Parameters.table_type`` marker. The
lookup is one moto ``get_table`` RTT (~5.9 ms measured on the compose
stack), so verdicts cache across statements under ``(database, table)`` —
repeated queries then pay a dict lookup instead of a Glue read.

Every catalog write the emulator can cause arrives as a submitted
statement, so ``iceberg_trino_submission`` calls ``invalidate`` whenever a
statement leads with a catalog-mutating verb; only writes that bypass the
emulator entirely (a consumer mutating moto Glue directly) rely on the TTL.
"""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic
from typing import Protocol

from athena_local.errors import MetadataException
from athena_local.glue_proxy import GlueProxy
from athena_local.iceberg_table import ICEBERG_TABLE_TYPE

# Bounds verdict staleness for catalog writes that bypass the emulator
# (direct moto clients); emulator-mediated writes clear the map on sight.
PROBE_TTL_SECONDS = 30.0
# Bounds retained verdicts on a long-lived process; insertion-order FIFO
# eviction, and an evicted key simply re-probes on its next reference.
MAX_CACHED_VERDICTS = 10_000


class IcebergTableProbe(Protocol):
    """Whether a Glue table is Iceberg (the ``table_type`` marker)."""

    def is_iceberg_table(self, database: str, table: str) -> bool: ...

    def invalidate(self) -> None:
        """Drop every cached verdict — a catalog-mutating statement ran."""
        ...


class GlueIcebergProbe:
    """Iceberg detection over moto Glue's ``Parameters`` map.

    Trino's Iceberg Glue registration writes ``table_type=ICEBERG`` plus the
    current ``metadata_location`` — the same marker AWS's Iceberg Glue
    integrations record — so a shared Glue read answers the routing
    question for tables created through either engine.

    Example::

        probe = GlueIcebergProbe(glue_proxy)
        probe.is_iceberg_table("analytics", "ice_t")  # True when Glue
        # Parameters carry table_type=ICEBERG, else False.
    """

    def __init__(
        self,
        glue: GlueProxy,
        *,
        ttl_seconds: float = PROBE_TTL_SECONDS,
        clock: Callable[[], float] = monotonic,
        max_verdicts: int = MAX_CACHED_VERDICTS,
    ) -> None:
        self._glue = glue
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._max_verdicts = max_verdicts
        self._verdicts: dict[tuple[str, str], tuple[bool, float]] = {}

    def is_iceberg_table(self, database: str, table: str) -> bool:
        key = (database.lower(), table.lower())
        hit = self._verdicts.get(key)
        if hit is not None and self._clock() - hit[1] < self._ttl_seconds:
            return hit[0]
        self._verdicts.pop(key, None)
        if len(self._verdicts) >= self._max_verdicts:
            self._verdicts.pop(next(iter(self._verdicts)))
        verdict = self._read(database, table)
        self._verdicts[key] = (verdict, self._clock())
        return verdict

    def invalidate(self) -> None:
        self._verdicts.clear()

    def _read(self, database: str, table: str) -> bool:
        try:
            metadata = self._glue.get_table(database, table)
        except MetadataException:
            return False
        parameters = metadata.parameters or {}
        return parameters.get("table_type", "").upper() == ICEBERG_TABLE_TYPE
