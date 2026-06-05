from __future__ import annotations

from typing import Protocol

from videos.core.domain.scene_spec import SceneSpec


class SceneBuilder(Protocol):
    def build(self, scene_spec: SceneSpec) -> object: ...
