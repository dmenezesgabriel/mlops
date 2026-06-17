"""ConceptExtension abstract base — bridges a Concept to its Narrative factory."""

from __future__ import annotations

from abc import ABC, abstractmethod

from videos.domain.entities.concept import Concept
from videos.domain.entities.narrative import Narrative


class ConceptExtension(ABC):
    @property
    @abstractmethod
    def concept(self) -> Concept: ...

    @abstractmethod
    def create_narrative(self) -> Narrative: ...
