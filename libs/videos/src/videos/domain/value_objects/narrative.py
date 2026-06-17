"""Beat value objects — BeatKind, NarrationLine, Beat."""

from __future__ import annotations

from dataclasses import field
from enum import Enum

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel


class BeatKind(Enum):
    OPENING = "opening"
    REVEAL = "reveal"
    EMPHASIS = "emphasis"
    TRANSITION = "transition"
    RECAP = "recap"


@dataclass(frozen=True)
class NarrationLine(PydanticModel):
    text: str
    duration_seconds: float

    @field_validator("duration_seconds")
    @classmethod
    def _duration_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError(
                f"NarrationLine.duration_seconds must be positive, got {v}"
            )
        if v > 15.0:
            raise ValueError(
                f"NarrationLine.duration_seconds must be <= 15.0, got {v}"
            )
        return v


@dataclass(frozen=True)
class Beat(PydanticModel):
    kind: BeatKind
    narration: NarrationLine
    visual_key: str
    params: dict[str, object] = field(default_factory=dict)
