"""ConceptRegistry entity — registry of ConceptExtensions."""

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
    """Registry of ConceptExtensions, injected into its consumers.

    Instance-scoped: callers own the registry they populate, so tests get
    isolation by constructing a fresh instance.

    Example:
        registry = ConceptRegistry()
        registry.register(my_extension)
        ext = registry.get(ConceptId(value="my_concept"))
    """

    def __init__(self) -> None:
        self._extensions: dict[str, ConceptExtension] = {}

    def register(self, extension: ConceptExtension) -> None:
        cid = extension.concept.id.value
        if cid in self._extensions:
            logger.warning("Overwriting extension", extra={"concept": cid})
        self._extensions[cid] = extension
        logger.info("Registered extension", extra={"concept": cid})

    def get(self, cid: ConceptId) -> ConceptExtension:
        if cid.value not in self._extensions:
            raise UnknownConceptError(cid.value, list(self._extensions))
        return self._extensions[cid.value]

    def all(self) -> tuple[ConceptExtension, ...]:
        return tuple(self._extensions.values())
