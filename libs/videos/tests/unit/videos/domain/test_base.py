from videos.domain.concept_extension import ConceptExtension


class TestConceptExtension:
    def test_extension_is_abstract(self) -> None:
        assert ConceptExtension.__abstractmethods__ != frozenset()
