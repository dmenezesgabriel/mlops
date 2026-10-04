from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        raise NotImplementedError

    def resolve_scene_preview_path(
        self, concept_id: str, scene_id: str
    ) -> Path:
        raise NotImplementedError
