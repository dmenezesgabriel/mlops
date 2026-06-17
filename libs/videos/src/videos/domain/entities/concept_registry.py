"""ConceptRegistry entity — global registry of ConceptExtensions."""

from __future__ import annotations

import logging

from videos.domain.entities.concept import ConceptId
from videos.domain.entities.concept_extension import ConceptExtension

logger = logging.getLogger(__name__)


class UnknownConceptError(LookupError):
    def __init__(self, concept_id: str, available: list[str]) -> None:
        super().__init__(
            f"Unknown concept {concept_id!r}. Available: {sorted(available)}"
        )


class ConceptRegistry:
    """Thread-unsafe singleton registry of ConceptExtensions.

    Example:
        ConceptRegistry.register(my_extension)
        ext = ConceptRegistry.get(ConceptId(value="my_concept"))
    """

    _extensions: dict[str, ConceptExtension] = {}

    @classmethod
    def register(cls, extension: ConceptExtension) -> None:
        cid = extension.concept.id.value
        if cid in cls._extensions:
            logger.warning("Overwriting extension", extra={"concept": cid})
        cls._extensions[cid] = extension
        logger.info("Registered extension", extra={"concept": cid})

    @classmethod
    def get(cls, cid: ConceptId) -> ConceptExtension:
        if cid.value not in cls._extensions:
            raise UnknownConceptError(cid.value, list(cls._extensions))
        return cls._extensions[cid.value]

    @classmethod
    def all(cls) -> tuple[ConceptExtension, ...]:
        return tuple(cls._extensions.values())
