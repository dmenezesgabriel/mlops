import sys

import pytest
from videos.domain.concept_registry import ConceptRegistry

# Remove local test folders from sys.path to prevent namespace collision with global manim library
sys.path = [
    p
    for p in sys.path
    if not p.endswith("infrastructure/manim")
    and not p.endswith("infrastructure")
    and "tests/integration" not in p.replace("\\", "/")
]


@pytest.fixture
def clear_registry() -> None:
    ConceptRegistry._extensions.clear()
