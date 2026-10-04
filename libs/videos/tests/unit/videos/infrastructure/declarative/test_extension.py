from __future__ import annotations

import pytest
from videos.infrastructure.declarative.extension import (
    DeclarativeConceptExtension,
)

SAMPLE_DATA: dict[str, object] = {
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
        # Valid concept metadata pins the raise to the extension's own
        # beats guard — a bare try/except also passes when an upstream
        # pydantic ValidationError names a different cause.
        with pytest.raises(
            ValueError, match="Narrative must have at least one beat for"
        ):
            DeclarativeConceptExtension({"concept": SAMPLE_DATA["concept"]})


class TestDeclarativeConceptExtensionShapeValidation:
    @pytest.mark.parametrize("bad_root", [[], "text", 42])
    def test_rejects_non_mapping_root(self, bad_root: object) -> None:
        with pytest.raises(ValueError, match="expected mapping"):
            DeclarativeConceptExtension(bad_root)

    def test_rejects_missing_concept(self) -> None:
        with pytest.raises(ValueError, match="expected mapping at concept"):
            DeclarativeConceptExtension({"narrative": {}})

    def test_rejects_non_mapping_concept(self) -> None:
        with pytest.raises(ValueError, match="expected mapping at concept"):
            DeclarativeConceptExtension({"concept": "x"})

    def test_rejects_non_mapping_narrative(self) -> None:
        with pytest.raises(ValueError, match="expected mapping at narrative"):
            DeclarativeConceptExtension({**SAMPLE_DATA, "narrative": 42})

    @pytest.mark.parametrize("narrative", [None, {}, {"beats": []}])
    def test_empty_narrative_reports_missing_beats(
        self, narrative: object
    ) -> None:
        # The extension's message — not Narrative's own validator ("Narrative
        # for 'x' must have at least one beat") — must be what fires.
        with pytest.raises(
            ValueError, match="Narrative must have at least one beat for"
        ):
            DeclarativeConceptExtension(
                {**SAMPLE_DATA, "narrative": narrative}
            )

    @pytest.mark.parametrize("bad_beats", [42, "ab"])
    def test_rejects_non_list_beats(self, bad_beats: object) -> None:
        data = {**SAMPLE_DATA, "narrative": {"beats": bad_beats}}
        with pytest.raises(
            ValueError, match=r"expected list at narrative\.beats"
        ):
            DeclarativeConceptExtension(data)

    def test_rejects_non_mapping_beat_element(self) -> None:
        data = {**SAMPLE_DATA, "narrative": {"beats": ["x"]}}
        with pytest.raises(
            ValueError, match=r"expected mapping at narrative\.beats\[0\]"
        ):
            DeclarativeConceptExtension(data)
