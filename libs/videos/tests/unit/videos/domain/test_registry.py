import pytest
from videos.domain.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.domain.concept_extension import ConceptExtension
from videos.domain.concept_registry import ConceptRegistry, UnknownConceptError
from videos.domain.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
    Narrative,
)


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
        id=ConceptId(id_str),
        metadata=ConceptMetadata(title=title, description="", tags=()),
    )


def test_register_stores_extension() -> None:
    registry = ConceptRegistry()
    ext = StubExtension(_concept("test-a"))
    registry.register(ext)
    assert registry.get(ConceptId("test-a")) is ext


def test_get_raises_unknown() -> None:
    registry = ConceptRegistry()
    with pytest.raises(UnknownConceptError, match="Unknown concept"):
        registry.get(ConceptId("does-not-exist"))


def test_all_returns_all_registered() -> None:
    registry = ConceptRegistry()
    registry.register(StubExtension(_concept("a")))
    registry.register(StubExtension(_concept("b")))
    result = registry.all()
    assert len(result) == 2


def test_register_overwrites_existing() -> None:
    registry = ConceptRegistry()
    newer = StubExtension(_concept("dup"))
    registry.register(StubExtension(_concept("dup")))
    registry.register(newer)
    assert registry.get(ConceptId("dup")) is newer


def test_instances_are_isolated() -> None:
    # Registrations live on the instance — a second registry must not see
    # them (the ClassVar singleton leaked them into every consumer).
    first = ConceptRegistry()
    second = ConceptRegistry()
    first.register(StubExtension(_concept("x")))
    with pytest.raises(UnknownConceptError):
        second.get(ConceptId("x"))
