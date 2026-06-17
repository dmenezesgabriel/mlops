import pytest
from videos.domain.entities.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.domain.entities.narrative import BeatKind, Narrative
from videos.domain.value_objects.narrative import Beat, NarrationLine


def _make_concept() -> Concept:
    return Concept(
        id=ConceptId(value="test"),
        metadata=ConceptMetadata(
            title=ConceptTitle(short="Test"),
            description="desc",
            tags=(),
        ),
    )


def _make_beat(kind: BeatKind) -> Beat:
    return Beat(
        kind=kind,
        narration=NarrationLine(text="Some text", duration_seconds=5.0),
        visual_key="key",
    )


class TestNarrative:
    def test_valid_narrative_creation(self) -> None:
        concept = _make_concept()
        narrative = Narrative(
            concept=concept,
            beats=(
                _make_beat(BeatKind.OPENING),
                _make_beat(BeatKind.RECAP),
            ),
        )
        assert narrative.concept == concept

    def test_narrative_rejects_empty_beats(self) -> None:
        with pytest.raises(ValueError, match="at least one beat"):
            Narrative(concept=_make_concept(), beats=())

    def test_narrative_rejects_non_opening_start(self) -> None:
        with pytest.raises(ValueError, match="OPENING"):
            Narrative(
                concept=_make_concept(),
                beats=(_make_beat(BeatKind.RECAP),),
            )

    def test_total_duration(self) -> None:
        narrative = Narrative(
            concept=_make_concept(),
            beats=(
                _make_beat(BeatKind.OPENING),
                _make_beat(BeatKind.RECAP),
            ),
        )
        assert narrative.total_duration == 10.0
