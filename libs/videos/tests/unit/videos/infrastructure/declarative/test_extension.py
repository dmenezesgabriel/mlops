from __future__ import annotations

from videos.infrastructure.declarative.extension import (
    DeclarativeConceptExtension,
)

SAMPLE_DATA: dict = {
    "concept": {
        "id": {"value": "test_concept"},
        "metadata": {
            "title": {"short": "Test", "subtitle": "Sub"},
            "description": "Desc",
            "tags": ["test"],
        },
    },
    "narrative": {
        "beats": [
            {
                "kind": "opening",
                "narration": {"text": "Open", "duration_seconds": 5.0},
                "visual_key": "open",
            },
            {
                "kind": "recap",
                "narration": {"text": "End", "duration_seconds": 4.0},
                "visual_key": "end",
            },
        ],
    },
}


class TestDeclarativeConceptExtension:
    def test_implements_concept_extension(self) -> None:
        ext = DeclarativeConceptExtension(SAMPLE_DATA)
        assert ext.concept.id.value == "test_concept"
        assert ext.concept.metadata.title.short == "Test"

    def test_create_narrative(self) -> None:
        ext = DeclarativeConceptExtension(SAMPLE_DATA)
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 2
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"

    def test_rejects_missing_narrative(self) -> None:
        raised = False
        try:
            DeclarativeConceptExtension(
                {"concept": {"id": {"value": "x"}, "metadata": {}}}
            )
        except Exception:
            raised = True
        assert raised

    def test_has_scenes_none_when_not_provided(self) -> None:
        ext = DeclarativeConceptExtension(SAMPLE_DATA)
        assert ext.scenes is None

    def test_parses_explicit_scenes(self) -> None:
        data = {**SAMPLE_DATA, "scenes": []}
        ext = DeclarativeConceptExtension(data)
        assert ext.scenes == ()
