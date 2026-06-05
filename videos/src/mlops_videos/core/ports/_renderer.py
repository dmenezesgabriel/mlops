from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from mlops_videos.core.ports._scene_builder import ScenePlan


class VideoRenderer(ABC):
    @abstractmethod
    def render(self, plan: ScenePlan, output_path: Path) -> Path: ...
