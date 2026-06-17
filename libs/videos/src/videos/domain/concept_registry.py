# Backward-compatible re-export — import from canonical location instead.
from videos.domain.entities.concept_registry import (
    ConceptRegistry,
    UnknownConceptError,
)

__all__ = ["ConceptRegistry", "UnknownConceptError"]
