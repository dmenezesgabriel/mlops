from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from mlops_videos.core._domain._narrative import Narrative


@dataclass(frozen=True)
class ScenePlan:
    narrative: Narrative


class NarrativeProvider(Protocol):
    def create_narrative(self) -> Narrative: ...


class SceneBuilder(ABC):
    @abstractmethod
    def plan(self, narrative: Narrative) -> ScenePlan: ...
