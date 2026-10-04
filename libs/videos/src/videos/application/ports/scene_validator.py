from __future__ import annotations

from typing import Protocol

from videos.domain.value_objects.quality import RuleViolation
from videos.domain.value_objects.scene_spec import SceneSpec


class SceneValidator(Protocol):
    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        raise NotImplementedError
