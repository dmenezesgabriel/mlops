"""Narrative entity — orchestrates a Concept's sequence of Beats."""

from __future__ import annotations

from pydantic import model_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel
from videos.domain.entities.concept import Concept
from videos.domain.value_objects.narrative import Beat, BeatKind


@dataclass(frozen=True)
class Narrative(PydanticModel):
    """A Concept's full narration plan.

    Must start with an OPENING beat and end with a RECAP beat.

    Example:
        Narrative(concept=concept, beats=(opening_beat, recap_beat))
    """

    concept: Concept
    beats: tuple[Beat, ...]

    @model_validator(mode="after")
    def _check_beat_invariants(self) -> Narrative:
        if not self.beats:
            raise ValueError(
                f"Narrative for {self.concept.id.value!r} must have at least "
                f"one beat, got empty"
            )
        if self.beats[0].kind != BeatKind.OPENING:
            raise ValueError(
                f"Narrative for {self.concept.id.value!r} must start with "
                f"OPENING beat, got {self.beats[0].kind.value!r}"
            )
        if self.beats[-1].kind != BeatKind.RECAP:
            raise ValueError(
                f"Narrative for {self.concept.id.value!r} must end with "
                f"RECAP beat, got {self.beats[-1].kind.value!r}"
            )
        return self

    @property
    def total_duration(self) -> float:
        return sum(b.narration.duration_seconds for b in self.beats)
