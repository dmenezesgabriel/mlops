from __future__ import annotations

from collections.abc import Sequence

from videos.core.domain._scene_spec import SceneSpec
from videos.core.domain._storyboard import Storyboard


class SceneCompiler:
    def compile(self, storyboard: Storyboard) -> Sequence[SceneSpec]:
        return storyboard.scenes
