import pytest
from videos.concepts.base import ConceptExtension
from videos.concepts.registry import ConceptRegistry, UnknownConceptError
from videos.core.domain.concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain.narrative import Beat, BeatKind, NarrationLine, Narrative


class StubExtension(ConceptExtension):
    def __init__(self, concept: Concept) -> None:
        self._concept = concept

    @property
    def concept(self) -> Concept:
        return self._concept

    def create_narrative(self) -> Narrative:
        return Narrative(
            self._concept,
            (
                Beat(BeatKind.OPENING, NarrationLine("s", 5.0), "o", {}),
                Beat(BeatKind.RECAP, NarrationLine("e", 5.0), "c", {}),
            ),
        )


def _concept(id_str: str) -> Concept:
    title = ConceptTitle(short=id_str, subtitle="")
    return Concept(
        id=ConceptId(id_str), metadata=ConceptMetadata(title=title, description="", tags=())
    )


@pytest.fixture(autouse=True)
def _clear() -> None:
    ConceptRegistry._extensions.clear()


def test_register_stores_extension() -> None:
    ext = StubExtension(_concept("test-a"))
    ConceptRegistry.register(ext)
    assert ConceptRegistry.get(ConceptId("test-a")) is ext


def test_get_raises_unknown() -> None:
    with pytest.raises(UnknownConceptError, match="Unknown concept"):
        ConceptRegistry.get(ConceptId("does-not-exist"))


def test_all_returns_all_registered() -> None:
    ext_a = StubExtension(_concept("a"))
    ext_b = StubExtension(_concept("b"))
    ConceptRegistry.register(ext_a)
    ConceptRegistry.register(ext_b)
    result = ConceptRegistry.all()
    assert len(result) == 2


def test_register_overwrites_existing() -> None:
    older = StubExtension(_concept("dup"))
    newer = StubExtension(_concept("dup"))
    ConceptRegistry.register(older)
    ConceptRegistry.register(newer)
    assert ConceptRegistry.get(ConceptId("dup")) is newer
