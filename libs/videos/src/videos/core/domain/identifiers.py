from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from videos.core.domain._base import PydanticModel


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


class ComponentType(StrEnum):
    TITLE = "title"
    TEXT = "text"
    DIAGRAM = "diagram"
    CYCLE = "cycle"
    TARGET = "target"
    LINEAR = "linear"
