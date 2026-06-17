# Backward-compatible re-export — import from canonical location instead.
from videos.domain.entities.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)

__all__ = ["Concept", "ConceptId", "ConceptTitle", "ConceptMetadata"]
