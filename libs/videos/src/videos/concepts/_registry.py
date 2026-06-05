from __future__ import annotations

import logging

from videos.concepts._base import ConceptExtension
from videos.core.domain._concept import ConceptId

logger = logging.getLogger(__name__)


class UnknownConceptError(LookupError):
    def __init__(self, concept_id: str, available: list[str]) -> None:
        super().__init__(f"Unknown concept {concept_id!r}. Available: {sorted(available)}")


class ConceptRegistry:
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
