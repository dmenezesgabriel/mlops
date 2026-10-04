"""Storyboard entity — an ordered sequence of SceneSpecs."""

from __future__ import annotations

from pydantic import model_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel
from videos.domain.value_objects.scene_spec import SceneSpec


@dataclass(frozen=True)
class Storyboard(PydanticModel):
    """Ordered set of scenes with uniqueness and non-empty invariants.

    Example:
        Storyboard(scenes=[SceneSpec(...)])
    """

    scenes: tuple[SceneSpec, ...]

    @model_validator(mode="after")
    def _check_scene_invariants(self) -> Storyboard:
        if not self.scenes:
            raise ValueError(
                "Storyboard must have at least one scene, got empty"
            )
        seen: set[str] = set()
        for scene in self.scenes:
            if scene.scene_id in seen:
                raise ValueError(
                    f"Duplicate scene_id in storyboard: {scene.scene_id!r}"
                )
            seen.add(scene.scene_id)
        return self
