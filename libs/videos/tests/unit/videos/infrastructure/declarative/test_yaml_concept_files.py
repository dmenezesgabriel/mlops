from __future__ import annotations

from pathlib import Path

import pytest
from videos.domain.concept import ConceptId
from videos.domain.concept_registry import ConceptRegistry
from videos.infrastructure.declarative import register_all


class TestYamlConceptDiscovery:
    def test_register_all_loads_concepts_from_directory(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        registry = ConceptRegistry()
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
        register_all(registry, definitions_dir=tmp_path)

        # Assert
        ext = registry.get(ConceptId("test_concept"))
        assert ext.concept.id.value == "test_concept"
        assert len(ext.create_narrative().beats) == 2

    def test_register_all_does_nothing_if_dir_not_provided(self) -> None:
        # Arrange
        registry = ConceptRegistry()

        # Act
        register_all(registry)

        # Assert
        assert len(registry.all()) == 0

    def test_register_all_fail_fast_names_bad_file(
        self, tmp_path: Path
    ) -> None:
        # Arrange — a malformed file aborts registration naming its path
        registry = ConceptRegistry()
        (tmp_path / "bad.yaml").write_text("- not\n- a\n- mapping\n")

        # Act & Assert
        with pytest.raises(ValueError) as excinfo:
            register_all(registry, definitions_dir=tmp_path)
        assert "bad.yaml" in str(excinfo.value)
