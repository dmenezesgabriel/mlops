from __future__ import annotations

from dataclasses import field
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import field_validator
from pydantic.dataclasses import dataclass

from videos.core.domain._base import PydanticModel

if TYPE_CHECKING:
    from videos.core.domain.concept import Concept


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
            raise ValueError(f"NarrationLine.duration_seconds must be positive, got {v}")
        if v > 15.0:
            raise ValueError(f"NarrationLine.duration_seconds must be <= 15.0, got {v}")
        return v


@dataclass(frozen=True)
class Beat(PydanticModel):
    kind: BeatKind
    narration: NarrationLine
    visual_key: str
    params: dict[str, object] = field(default_factory=dict)


class Narrative:
    def __init__(self, concept: Concept, beats: tuple[Beat, ...]) -> None:
        if not beats:
            raise ValueError(
                f"Narrative for {concept.id.value!r} must have at least one beat, got empty"
            )
        if beats[0].kind != BeatKind.OPENING:
            raise ValueError(
                f"Narrative for {concept.id.value!r} must start with OPENING beat, "
                f"got {beats[0].kind.value!r}"
            )
        if beats[-1].kind != BeatKind.RECAP:
            raise ValueError(
                f"Narrative for {concept.id.value!r} must end with RECAP beat, "
                f"got {beats[-1].kind.value!r}"
            )
        self._concept = concept
        self._beats = beats

    @property
    def concept(self) -> Concept:
        return self._concept

    @property
    def beats(self) -> tuple[Beat, ...]:
        return self._beats

    @property
    def total_duration(self) -> float:
        return sum(b.narration.duration_seconds for b in self._beats)
