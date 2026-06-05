import importlib

from videos.concepts._registry import ConceptRegistry
from videos.core.domain._concept import ConceptId


class TestUnderfitVsOverfit:
    def test_concept_is_registered(self) -> None:
        ConceptRegistry._extensions.clear()
        import videos.concepts.underfit_vs_overfit as mod

        importlib.reload(mod)
        ext = ConceptRegistry.get(ConceptId("underfit_vs_overfit"))
        assert ext.concept.id.value == "underfit_vs_overfit"

    def test_narrative_has_expected_structure(self) -> None:
        ConceptRegistry._extensions.clear()
        import videos.concepts.underfit_vs_overfit as mod

        importlib.reload(mod)
        ext = ConceptRegistry.get(ConceptId("underfit_vs_overfit"))
        narrative = ext.create_narrative()
        assert len(narrative.beats) > 0
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"
