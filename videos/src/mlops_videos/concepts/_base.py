from __future__ import annotations

from abc import ABC, abstractmethod

from mlops_videos.core._domain._concept import Concept
from mlops_videos.core._domain._narrative import Narrative


class ConceptExtension(ABC):
    @property
    @abstractmethod
    def concept(self) -> Concept: ...

    @abstractmethod
    def create_narrative(self) -> Narrative: ...
