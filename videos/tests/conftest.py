import pytest
from mlops_videos.concepts._registry import ConceptRegistry


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    ConceptRegistry._extensions.clear()
