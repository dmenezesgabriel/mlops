from __future__ import annotations

from pathlib import Path

from videos.domain.concept import ConceptId
from videos.domain.concept_registry import ConceptRegistry
from videos.infrastructure.declarative import register_all


class TestYamlConceptDiscovery:
    def test_register_all_loads_concepts_from_directory(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        ConceptRegistry._extensions.clear()
        yaml_content = """
concept:
  id: test_concept
  metadata:
    title:
      short: Test
      subtitle: Sub
    description: Desc
    tags: [test]
narrative:
  beats:
    - kind: opening
      narration: {text: "Open", duration_seconds: 5.0}
      visual_key: title
    - kind: recap
      narration: {text: "End", duration_seconds: 5.0}
      visual_key: recap
"""
        yaml_path = tmp_path / "test_concept.yaml"
        yaml_path.write_text(yaml_content)

        # Act
        register_all(definitions_dir=tmp_path)

        # Assert
        ext = ConceptRegistry.get(ConceptId("test_concept"))
        assert ext.concept.id.value == "test_concept"
        assert len(ext.create_narrative().beats) == 2

    def test_register_all_does_nothing_if_dir_not_provided(self) -> None:
        # Arrange
        ConceptRegistry._extensions.clear()

        # Act
        register_all()

        # Assert
        assert len(ConceptRegistry.all()) == 0
