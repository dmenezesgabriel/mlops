import importlib

from videos.concepts._registry import ConceptRegistry
from videos.core.domain._concept import ConceptId


class TestBiasVarianceTradeoff:
    def test_concept_is_registered(self) -> None:
        ConceptRegistry._extensions.clear()
        import videos.concepts.bias_variance_tradeoff as mod

        importlib.reload(mod)
        ext = ConceptRegistry.get(ConceptId("bias_variance_tradeoff"))
        assert ext.concept.id.value == "bias_variance_tradeoff"

    def test_narrative_has_expected_structure(self) -> None:
        ConceptRegistry._extensions.clear()
        import videos.concepts.bias_variance_tradeoff as mod

        importlib.reload(mod)
        ext = ConceptRegistry.get(ConceptId("bias_variance_tradeoff"))
        narrative = ext.create_narrative()
        assert len(narrative.beats) > 0
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"
