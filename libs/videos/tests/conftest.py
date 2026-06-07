import pytest
from videos.domain.concept_registry import ConceptRegistry


@pytest.fixture
def clear_registry() -> None:
    ConceptRegistry._extensions.clear()
