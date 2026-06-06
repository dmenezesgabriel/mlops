from __future__ import annotations

from typing import Protocol

from videos.core.domain.scene_spec import SceneSpec
from videos.core.domain.storyboard import Storyboard
from videos.core.ports.layout_engine import LayoutEngine


class SceneBuilder(Protocol):
    def build(self, scene_spec: SceneSpec) -> object: ...

    def build_storyboard(
        self, storyboard: Storyboard, layout_engine: LayoutEngine
    ) -> object: ...
