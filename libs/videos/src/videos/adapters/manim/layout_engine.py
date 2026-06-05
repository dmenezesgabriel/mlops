from __future__ import annotations

from videos.core.domain.layout import LayoutSpec
from videos.core.domain.scene_spec import SceneSpec


class ManimLayoutEngine:
    def apply(self, scene: SceneSpec) -> SceneSpec:
        # Stub -- returns the scene unchanged.
        # TODO: implement actual Manim layout placement.
        return scene

    def validate_placement(self, layout: LayoutSpec) -> list[str]:
        return []
