from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Linter(Protocol):
    def verify_visuals(self, image_path: Path, scene_id: str) -> None:
        raise NotImplementedError

    def verify_video(self, video_path: Path, scene_id: str) -> None:
        raise NotImplementedError
