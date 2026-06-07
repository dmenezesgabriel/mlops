from videos.domain.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)


def test_concept_id_rejects_empty_string() -> None:
    raised = False
    try:
        ConceptId("")
    except ValueError:
        raised = True
    assert raised


def test_concept_id_rejects_whitespace_only() -> None:
    raised = False
    try:
        ConceptId("   ")
    except ValueError:
        raised = True
    assert raised


def test_concept_id_stores_value() -> None:
    cid = ConceptId("crisp-dm")
    assert cid.value == "crisp-dm"


def test_concept_id_equal_when_same_value() -> None:
    assert ConceptId("mlops") == ConceptId("mlops")


def test_concept_id_not_equal_when_different() -> None:
    assert ConceptId("a") != ConceptId("b")


def test_concept_id_hashable() -> None:
    lookup = {ConceptId("x"): 1}
    assert lookup[ConceptId("x")] == 1


def test_concept_id_repr_includes_value() -> None:
    assert repr(ConceptId("foo")) == "ConceptId('foo')"


def test_concept_title_stores_values() -> None:
    title = ConceptTitle(short="CRISP-DM", subtitle="A practical loop")
    assert title.short == "CRISP-DM"
    assert title.subtitle == "A practical loop"


def test_concept_title_rejects_empty_short() -> None:
    raised = False
    try:
        ConceptTitle(short="", subtitle="something")
    except ValueError:
        raised = True
    assert raised


def test_concept_title_allows_empty_subtitle() -> None:
    title = ConceptTitle(short="Bias-Variance", subtitle="")
    assert title.short == "Bias-Variance"
    assert title.subtitle == ""


def test_concept_metadata_stores_fields() -> None:
    title = ConceptTitle(short="CRISP-DM", subtitle="A loop")
    meta = ConceptMetadata(
        title=title, description="Desc", tags=("ml", "process")
    )
    assert meta.title.short == "CRISP-DM"
    assert meta.description == "Desc"
    assert meta.tags == ("ml", "process")


def test_concept_stores_id_and_metadata() -> None:
    cid = ConceptId("test")
    title = ConceptTitle(short="Test", subtitle="")
    meta = ConceptMetadata(title=title, description="", tags=())
    concept = Concept(id=cid, metadata=meta)
    assert concept.id == cid
    assert concept.metadata == meta
