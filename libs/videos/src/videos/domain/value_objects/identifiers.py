"""Identifier value objects — QualityLevel."""

from __future__ import annotations

from enum import StrEnum


class QualityLevel(StrEnum):
    PREVIEW = "preview"
    FINAL = "final"


def require_quality(value: str) -> str:
    """Reject a quality string outside the QualityLevel set.

    Used at every seam a raw `quality` string enters (context, artifact
    store, renderer) — produce()-level validation alone can't reach direct
    calls on those seams.
    """
    valid = sorted(level.value for level in QualityLevel)
    if value not in valid:
        raise ValueError(f"quality must be one of {valid}, got {value!r}")
    return value
