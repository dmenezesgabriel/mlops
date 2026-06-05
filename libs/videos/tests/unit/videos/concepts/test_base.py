from videos.concepts._base import ConceptExtension


class TestConceptExtension:
    def test_extension_is_abstract(self) -> None:
        import pytest

        with pytest.raises(TypeError):
            ConceptExtension()
