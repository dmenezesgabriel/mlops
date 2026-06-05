from __future__ import annotations

from pathlib import Path

from videos.concepts.registry import ConceptRegistry
from videos.declarative.discovery import find_concept_yaml_files
from videos.declarative.loader import load_concept_from_yaml_file
from videos.core.domain.concept import ConceptId


YAML_DIR = Path(__file__).parents[5] / "videos" / "src" / "videos" / "concepts" / "yaml"


class TestYamlConceptFiles:
    def test_yaml_directory_exists(self) -> None:
        assert YAML_DIR.is_dir()

    def test_finds_yaml_files(self) -> None:
        files = find_concept_yaml_files(YAML_DIR)
        assert len(files) >= 4

    def test_load_bias_variance(self) -> None:
        path = YAML_DIR / "bias_variance_tradeoff.yaml"
        ext = load_concept_from_yaml_file(str(path))
        assert ext.concept.id.value == "bias_variance_tradeoff"
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 9
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"

    def test_load_crisp_dm(self) -> None:
        path = YAML_DIR / "crisp_dm.yaml"
        ext = load_concept_from_yaml_file(str(path))
        assert ext.concept.id.value == "crisp_dm"
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 12
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"

    def test_load_mlops_lifecycle(self) -> None:
        path = YAML_DIR / "mlops_lifecycle.yaml"
        ext = load_concept_from_yaml_file(str(path))
        assert ext.concept.id.value == "mlops_lifecycle"
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 12
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"

    def test_load_underfit_vs_overfit(self) -> None:
        path = YAML_DIR / "underfit_vs_overfit.yaml"
        ext = load_concept_from_yaml_file(str(path))
        assert ext.concept.id.value == "underfit_vs_overfit"
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 8
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"

    def test_register_via_register_all(self) -> None:
        ConceptRegistry._extensions.clear()
        from videos.concepts import register_all

        register_all()
        ext = ConceptRegistry.get(ConceptId("bias_variance_tradeoff"))
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 9
