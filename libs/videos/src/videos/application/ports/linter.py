from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from videos.domain.value_objects.quality import RuleViolation


class Linter(Protocol):
    def verify_geometry(
        self, mobjects: list[Any], scene_id: str
    ) -> list[RuleViolation]:
        raise NotImplementedError

    def verify_visuals(self, image_path: Path, scene_id: str) -> None:
        raise NotImplementedError

    def verify_video(self, video_path: Path, scene_id: str) -> None:
        raise NotImplementedError
