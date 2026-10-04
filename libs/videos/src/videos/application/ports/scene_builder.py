from __future__ import annotations

from typing import Protocol

from videos.application.ports.layout_engine import LayoutEngine
from videos.domain.entities.storyboard import Storyboard
from videos.domain.value_objects.scene_spec import SceneSpec


class SceneBuilder(Protocol):
    def build(self, scene_spec: SceneSpec) -> object:
        raise NotImplementedError

    def build_storyboard(
        self, storyboard: Storyboard, layout_engine: LayoutEngine
    ) -> object:
        raise NotImplementedError
