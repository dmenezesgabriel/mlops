"""Beat value objects — BeatKind, NarrationLine, Beat."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

from pydantic import Field, field_serializer, field_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel, freeze_mapping


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
    params: Mapping[str, object] = Field(
        default_factory=dict, validate_default=True
    )

    @field_validator("params")
    @classmethod
    def _params_immutable(
        cls, v: Mapping[str, object]
    ) -> Mapping[str, object]:
        return freeze_mapping(v)

    @field_serializer("params")
    def _serialize_params(self, v: Mapping[str, object]) -> dict[str, object]:
        return dict(v)
