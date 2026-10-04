"""Identifier value objects — SceneId, QualityLevel, ComponentType."""

from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel


@dataclass(frozen=True)
class SceneId(PydanticModel):
    value: str

    @field_validator("value")
    @classmethod
    def _must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError(f"SceneId must not be empty, got {v!r}")
        return v

    def __repr__(self) -> str:
        return f"SceneId({self.value!r})"


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


class ComponentType(StrEnum):
    TITLE = "title"
    TEXT = "text"
    DIAGRAM = "diagram"
    CYCLE = "cycle"
    TARGET = "target"
    LINEAR = "linear"
