from __future__ import annotations

from videos.core.domain.concept import ConceptId
from videos.declarative.loader import yaml_to_concept_extension

SAMPLE_YAML = """
concept:
  id: test_concept
  metadata:
    title:
      short: Test Concept
      subtitle: A subtitle
    description: A test concept
    tags: [test, demo]

narrative:
  beats:
    - kind: opening
      narration:
        text: "Opening text"
        duration_seconds: 5.0
      visual_key: title
    - kind: reveal
      narration:
        text: "Reveal text"
        duration_seconds: 4.0
      visual_key: content
    - kind: recap
      narration:
        text: "Recap text"
        duration_seconds: 3.0
      visual_key: recap
"""


class TestYamlToConceptExtension:
    def test_loads_concept_metadata(self) -> None:
        ext = yaml_to_concept_extension(SAMPLE_YAML)
        assert ext.concept.id == ConceptId("test_concept")
        assert ext.concept.metadata.title.short == "Test Concept"

    def test_loads_narrative_beats(self) -> None:
        ext = yaml_to_concept_extension(SAMPLE_YAML)
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 3
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[1].kind.value == "reveal"
        assert narrative.beats[-1].kind.value == "recap"

    def test_loads_narration_text(self) -> None:
        ext = yaml_to_concept_extension(SAMPLE_YAML)
        narrative = ext.create_narrative()
        assert narrative.beats[0].narration.text == "Opening text"
        assert narrative.beats[0].narration.duration_seconds == 5.0

    def test_validates_beat_kind(self) -> None:
        bad_yaml = SAMPLE_YAML.replace("opening", "invalid_kind")
        raised = False
        try:
            yaml_to_concept_extension(bad_yaml)
        except Exception:
            raised = True
        assert raised

    def test_registers_with_registry(self) -> None:
        from videos.concepts.registry import ConceptRegistry

        ConceptRegistry._extensions.clear()
        ext = yaml_to_concept_extension(SAMPLE_YAML)
        ConceptRegistry.register(ext)
        retrieved = ConceptRegistry.get(ConceptId("test_concept"))
        assert retrieved is ext
