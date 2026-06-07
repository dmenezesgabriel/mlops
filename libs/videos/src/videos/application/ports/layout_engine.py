from __future__ import annotations

from typing import Protocol

from videos.domain.layout import LayoutSpec
from videos.domain.scene_spec import SceneSpec


class LayoutEngine(Protocol):
    def apply(self, scene: SceneSpec) -> SceneSpec: ...

    def validate_placement(self, layout: LayoutSpec) -> list[str]: ...
