from videos.concepts import register_all
from videos.concepts.registry import ConceptRegistry
from videos.core.domain.concept import ConceptId


class TestMlopsLifecycle:
    def test_concept_is_registered(self) -> None:
        ConceptRegistry._extensions.clear()
        register_all()
        ext = ConceptRegistry.get(ConceptId("mlops_lifecycle"))
        assert ext.concept.id.value == "mlops_lifecycle"

    def test_narrative_has_expected_structure(self) -> None:
        ConceptRegistry._extensions.clear()
        register_all()
        ext = ConceptRegistry.get(ConceptId("mlops_lifecycle"))
        narrative = ext.create_narrative()
        assert len(narrative.beats) > 0
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"
