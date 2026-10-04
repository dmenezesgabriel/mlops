from __future__ import annotations

from typing import Protocol

from videos.domain.value_objects.scene_spec import SceneSpec


class LayoutEngine(Protocol):
    def apply(self, scene: SceneSpec) -> SceneSpec:
        raise NotImplementedError
