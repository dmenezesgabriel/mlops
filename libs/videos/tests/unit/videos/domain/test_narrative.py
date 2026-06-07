import pytest
from videos.domain.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.domain.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
    Narrative,
)


def _make_concept(id_str: str = "test") -> Concept:
    title = ConceptTitle(short="Test", subtitle="")
    meta = ConceptMetadata(title=title, description="", tags=())
    return Concept(id=ConceptId(id_str), metadata=meta)


def _beat(
    kind: BeatKind = BeatKind.REVEAL, duration: float = 2.0, visual: str = "x"
) -> Beat:
    return Beat(
        kind=kind,
        narration=NarrationLine(text="hello", duration_seconds=duration),
        visual_key=visual,
        params={},
    )


class TestNarrationLine:
    def test_rejects_zero_duration(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds"):
            NarrationLine(text="x", duration_seconds=0.0)

    def test_rejects_negative_duration(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds"):
            NarrationLine(text="x", duration_seconds=-1.0)

    def test_rejects_duration_over_15(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds"):
            NarrationLine(text="x", duration_seconds=15.1)

    def test_accepts_valid_duration(self) -> None:
        line = NarrationLine(text="hello", duration_seconds=5.0)
        assert line.text == "hello"
        assert line.duration_seconds == 5.0


class TestBeatKind:
    def test_has_expected_members(self) -> None:
        values = {k.value for k in BeatKind}
        assert values == {
            "opening",
            "reveal",
            "emphasis",
            "transition",
            "recap",
        }


class TestNarrative:
    def test_rejects_empty_beats(self) -> None:
        with pytest.raises(ValueError, match="at least one beat"):
            Narrative(concept=_make_concept(), beats=())

    def test_rejects_missing_opening(self) -> None:
        with pytest.raises(ValueError, match="OPENING"):
            Narrative(concept=_make_concept(), beats=(_beat(BeatKind.REVEAL),))

    def test_rejects_missing_recap(self) -> None:
        with pytest.raises(ValueError, match="RECAP"):
            Narrative(
                concept=_make_concept(), beats=(_beat(BeatKind.OPENING),)
            )

    def test_accepts_valid_sequence(self) -> None:
        beats = (
            _beat(BeatKind.OPENING),
            _beat(BeatKind.REVEAL),
            _beat(BeatKind.RECAP),
        )
        narrative = Narrative(concept=_make_concept(), beats=beats)
        assert len(narrative.beats) == 3

    def test_total_duration_sums_beats(self) -> None:
        beats = (
            _beat(BeatKind.OPENING, 3.0),
            _beat(BeatKind.REVEAL, 4.0),
            _beat(BeatKind.RECAP, 3.0),
        )
        narrative = Narrative(concept=_make_concept(), beats=beats)
        assert narrative.total_duration == 10.0

    def test_concept_is_stored(self) -> None:
        concept = _make_concept("crisp-dm")
        beats = (_beat(BeatKind.OPENING), _beat(BeatKind.RECAP))
        narrative = Narrative(concept=concept, beats=beats)
        assert narrative.concept.id.value == "crisp-dm"

    def test_beats_are_immutable(self) -> None:
        beats = (_beat(BeatKind.OPENING), _beat(BeatKind.RECAP))
        narrative = Narrative(concept=_make_concept(), beats=beats)
        assert isinstance(narrative.beats, tuple)
