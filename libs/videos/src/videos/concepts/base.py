from __future__ import annotations

from abc import ABC, abstractmethod

from videos.core.domain.concept import Concept
from videos.core.domain.narrative import Narrative


class ConceptExtension(ABC):
    @property
    @abstractmethod
    def concept(self) -> Concept: ...

    @abstractmethod
    def create_narrative(self) -> Narrative: ...
