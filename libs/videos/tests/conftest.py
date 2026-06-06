import pytest

from videos.concepts.registry import ConceptRegistry


@pytest.fixture
def clear_registry() -> None:
    ConceptRegistry._extensions.clear()
