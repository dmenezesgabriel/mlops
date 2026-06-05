from __future__ import annotations

from collections.abc import Sequence

from videos.core.domain.scene_spec import SceneSpec


class Storyboard:
    def __init__(self, scenes: Sequence[SceneSpec]) -> None:
        if not scenes:
            raise ValueError("Storyboard must have at least one scene, got empty")
        seen: set[str] = set()
        for scene in scenes:
            if scene.scene_id in seen:
                raise ValueError(f"Duplicate scene_id in storyboard: {scene.scene_id!r}")
            seen.add(scene.scene_id)
        self._scenes = list(scenes)

    @property
    def scenes(self) -> tuple[SceneSpec, ...]:
        return tuple(self._scenes)

    @property
    def total_expected_duration(self) -> float:
        return sum(s.duration_seconds for s in self._scenes)
