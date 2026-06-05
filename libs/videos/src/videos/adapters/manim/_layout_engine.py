from __future__ import annotations

from videos.core.domain._layout import LayoutSpec
from videos.core.domain._scene_spec import SceneSpec


class ManimLayoutEngine:
    def apply(self, scene: SceneSpec) -> SceneSpec:
        return scene

    def validate_placement(self, layout: LayoutSpec) -> list[str]:
        return []
