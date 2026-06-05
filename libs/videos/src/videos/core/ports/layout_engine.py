from __future__ import annotations

from typing import Protocol

from videos.core.domain.layout import LayoutSpec
from videos.core.domain.scene_spec import SceneSpec


class LayoutEngine(Protocol):
    def apply(self, scene: SceneSpec) -> SceneSpec: ...

    def validate_placement(self, layout: LayoutSpec) -> list[str]: ...
