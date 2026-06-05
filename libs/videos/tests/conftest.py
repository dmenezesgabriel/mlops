import pytest
from videos.concepts._registry import ConceptRegistry


@pytest.fixture
def clear_registry() -> None:
    ConceptRegistry._extensions.clear()
