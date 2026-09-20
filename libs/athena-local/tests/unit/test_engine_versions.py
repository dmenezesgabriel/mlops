"""Handler tests for ListEngineVersions (MD-5).

The operation returns the pinned engine version list: the emulator's sole
engine is the Trino-backed Athena engine 3, mirroring the workgroup default
(moto ``research_repos/moto/moto/athena/models.py:80-83``). Output shape
follows the canonical ``ListEngineVersionsOutput`` (``EngineVersions``
member, no NextToken for a single-entry list).
"""

from __future__ import annotations

from athena_local.dispatch import implemented_operations
from athena_local.engine_versions import list_engine_versions


def test_list_engine_versions_operation_is_registered() -> None:
    import athena_local.main  # noqa: F401

    assert "ListEngineVersions" in implemented_operations()


def test_list_engine_versions_returns_pinned_engine() -> None:
    output = list_engine_versions(None)

    assert output["EngineVersions"] == [
        {
            "SelectedEngineVersion": "AUTO",
            "EffectiveEngineVersion": "Athena engine version 3",
        }
    ]


def test_list_engine_versions_has_no_next_token() -> None:
    output = list_engine_versions(None)

    assert "NextToken" not in output


def test_list_engine_versions_accepts_pagination_keywords() -> None:
    output = list_engine_versions({"MaxResults": 5, "NextToken": "abc"})

    assert len(output["EngineVersions"]) == 1
    assert "NextToken" not in output
