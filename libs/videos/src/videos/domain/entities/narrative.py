"""Narrative entity — orchestrates a Concept's sequence of Beats."""

from __future__ import annotations

from videos.domain.entities.concept import Concept
from videos.domain.value_objects.narrative import Beat, BeatKind


class Narrative:
    """A Concept's full narration plan.

    Must start with an OPENING beat and end with a RECAP beat.

    Example:
        Narrative(concept=concept, beats=(opening_beat, recap_beat))
    """

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
