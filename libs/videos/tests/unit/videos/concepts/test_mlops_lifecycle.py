import importlib

from videos.concepts._registry import ConceptRegistry
from videos.core.domain._concept import ConceptId


class TestMlopsLifecycle:
    def test_concept_is_registered(self) -> None:
        ConceptRegistry._extensions.clear()
        import videos.concepts.mlops_lifecycle as mod

        importlib.reload(mod)
        ext = ConceptRegistry.get(ConceptId("mlops_lifecycle"))
        assert ext.concept.id.value == "mlops_lifecycle"

    def test_narrative_has_expected_structure(self) -> None:
        ConceptRegistry._extensions.clear()
        import videos.concepts.mlops_lifecycle as mod

        importlib.reload(mod)
        ext = ConceptRegistry.get(ConceptId("mlops_lifecycle"))
        narrative = ext.create_narrative()
        assert len(narrative.beats) > 0
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"
