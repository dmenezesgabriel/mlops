import pytest
from pydantic import ValidationError
from videos.domain.entities.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)


class TestConcept:
    def test_valid_concept_creation(self) -> None:
        concept = Concept(
            id=ConceptId(value="mlops_101"),
            metadata=ConceptMetadata(
                title=ConceptTitle(short="MLOps 101"),
                description="An intro.",
                tags=("mlops",),
            ),
        )
        assert concept.id.value == "mlops_101"

    def test_concept_id_requires_non_empty(self) -> None:
        with pytest.raises(ValidationError):
            ConceptId(value="")

    def test_concept_title_requires_non_empty_short(self) -> None:
        with pytest.raises(ValidationError):
            ConceptTitle(short="")
