"""ListEngineVersions operation (MD-5): handler bound into the dispatch registry.

The emulator exposes exactly one engine — the Trino-backed Athena engine 3 —
so the pinned list is a single entry matching the workgroup default engine
(moto ``research_repos/moto/moto/athena/models.py:80-83``). Pagination inputs
are accepted for model compat and answered with no NextToken: a one-entry list
never needs a second page.
"""

from __future__ import annotations

from athena_local.common_schemas import DEFAULT_ENGINE_VERSION
from athena_local.dispatch import register_handler


def _pinned_engine_versions() -> list[dict[str, object]]:
    return [
        {
            "SelectedEngineVersion": DEFAULT_ENGINE_VERSION.selected_engine_version,
            "EffectiveEngineVersion": DEFAULT_ENGINE_VERSION.effective_engine_version,
        }
    ]


def list_engine_versions(
    _payload: dict[str, object] | None,
) -> dict[str, object]:
    return {"EngineVersions": _pinned_engine_versions()}


def register_engine_version_handlers() -> None:
    """Bind ListEngineVersions (explicit wiring; no store dependency)."""
    register_handler("ListEngineVersions", list_engine_versions)
