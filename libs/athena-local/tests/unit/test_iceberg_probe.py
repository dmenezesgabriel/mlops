"""Unit tests for ``iceberg_probe.py`` — the Iceberg verdict probe + cache.

The probe answers one question per (database, table): does Glue's
``Parameters.table_type`` marker say ICEBERG — the registration Trino's
Iceberg Glue catalog writes (ADR-0013). Each lookup costs a moto Glue RTT,
so verdicts cache across statements; ``invalidate`` drops the map when a
catalog-mutating statement goes by, and a TTL bounds staleness from writes
that bypass the emulator entirely.
"""

from __future__ import annotations

from athena_local.glue_proxy import GlueProxy
from athena_local.iceberg_probe import GlueIcebergProbe
from tests.unit._glue_fakes import FakeGlueClient

ICEBERG_TABLE = {
    "analytics": [{"Name": "t", "Parameters": {"table_type": "ICEBERG"}}]
}


def _probe(
    tables: dict[str, list[dict[str, object]]],
    **kwargs: object,
) -> GlueIcebergProbe:
    return GlueIcebergProbe(GlueProxy(FakeGlueClient(tables=tables)), **kwargs)


class TestGlueIcebergProbe:
    def test_table_type_iceberg_is_detected(self) -> None:
        probe = _probe(ICEBERG_TABLE)
        assert probe.is_iceberg_table("analytics", "t") is True

    def test_table_type_value_matches_case_insensitively(self) -> None:
        probe = _probe(
            {
                "analytics": [
                    {"Name": "t", "Parameters": {"table_type": "iceberg"}}
                ]
            }
        )
        assert probe.is_iceberg_table("analytics", "t") is True

    def test_missing_table_is_not_iceberg(self) -> None:
        probe = _probe({})
        assert probe.is_iceberg_table("analytics", "t") is False

    def test_table_without_parameters_is_not_iceberg(self) -> None:
        probe = _probe({"analytics": [{"Name": "t"}]})
        assert probe.is_iceberg_table("analytics", "t") is False

    def test_hive_table_parameters_are_not_iceberg(self) -> None:
        probe = _probe(
            {"analytics": [{"Name": "t", "Parameters": {"EXTERNAL": "TRUE"}}]}
        )
        assert probe.is_iceberg_table("analytics", "t") is False


class TestVerdictCache:
    def _client(self) -> FakeGlueClient:
        return FakeGlueClient(tables=dict(ICEBERG_TABLE))

    def test_verdict_is_served_from_cache_on_repeat_lookup(self) -> None:
        client = self._client()
        probe = GlueIcebergProbe(GlueProxy(client))
        assert probe.is_iceberg_table("analytics", "t") is True
        assert probe.is_iceberg_table("analytics", "t") is True
        assert client.get_table_calls == [("analytics", "t")]

    def test_missing_table_verdict_is_cached(self) -> None:
        client = FakeGlueClient(tables={})
        probe = GlueIcebergProbe(GlueProxy(client))
        assert probe.is_iceberg_table("analytics", "gone") is False
        assert probe.is_iceberg_table("analytics", "gone") is False
        assert client.get_table_calls == [("analytics", "gone")]

    def test_invalidate_forces_a_fresh_lookup(self) -> None:
        client = self._client()
        probe = GlueIcebergProbe(GlueProxy(client))
        probe.is_iceberg_table("analytics", "t")
        probe.invalidate()
        assert probe.is_iceberg_table("analytics", "t") is True
        assert client.get_table_calls == [("analytics", "t")] * 2

    def test_entry_expires_after_ttl(self) -> None:
        now = [1000.0]
        client = self._client()
        probe = GlueIcebergProbe(
            GlueProxy(client), ttl_seconds=30.0, clock=lambda: now[0]
        )
        probe.is_iceberg_table("analytics", "t")
        now[0] += 29.0
        probe.is_iceberg_table("analytics", "t")
        now[0] += 2.0
        probe.is_iceberg_table("analytics", "t")
        assert client.get_table_calls == [("analytics", "t")] * 2

    def test_oldest_entry_evicts_at_capacity(self) -> None:
        tables = {
            "analytics": [
                {"Name": name, "Parameters": {"table_type": "ICEBERG"}}
                for name in ("a", "b", "c")
            ]
        }
        client = FakeGlueClient(tables=tables)
        probe = GlueIcebergProbe(GlueProxy(client), max_verdicts=2)
        probe.is_iceberg_table("analytics", "a")
        probe.is_iceberg_table("analytics", "b")
        probe.is_iceberg_table("analytics", "c")  # evicts "a"
        probe.is_iceberg_table("analytics", "b")  # still cached
        probe.is_iceberg_table("analytics", "a")  # re-probed
        assert client.get_table_calls == [
            ("analytics", "a"),
            ("analytics", "b"),
            ("analytics", "c"),
            ("analytics", "a"),
        ]

    def test_cache_key_folds_identifier_case(self) -> None:
        client = self._client()
        probe = GlueIcebergProbe(GlueProxy(client))
        probe.is_iceberg_table("Analytics", "T")
        probe.is_iceberg_table("analytics", "t")
        assert client.get_table_calls == [("Analytics", "T")]
