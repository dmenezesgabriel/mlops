from __future__ import annotations

from pathlib import Path

from videos.domain._base import require_slug
from videos.domain.value_objects.identifiers import require_quality


class FileSystemArtifactStore:
    def __init__(
        self,
        output_root: Path,
        preview_subdir: str = "previews",
        final_subdir: str = "final",
        scenes_subdir: str = "scenes",
    ) -> None:
        self._output_root = output_root
        self._preview_dir = output_root / preview_subdir
        self._final_dir = output_root / final_subdir
        self._scenes_dir = self._preview_dir / scenes_subdir

        self._preview_dir.mkdir(parents=True, exist_ok=True)
        self._final_dir.mkdir(parents=True, exist_ok=True)
        self._scenes_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _concept_filename(concept_id: str) -> str:
        # Validated at the sink too: a direct store call bypasses the VO
        # boundary, and an unbounded id escapes the output dirs via "../".
        return f"{require_slug(concept_id, 'concept_id')}.mp4"

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        require_quality(quality)
        if quality == "final":
            return self._final_dir / self._concept_filename(concept_id)
        return self._preview_dir / self._concept_filename(concept_id)

    def resolve_scene_preview_path(
        self, concept_id: str, scene_id: str
    ) -> Path:
        concept_slug = require_slug(concept_id, "concept_id")
        scene_slug = require_slug(scene_id, "scene_id")
        return self._scenes_dir / f"{concept_slug}_{scene_slug}.mp4"
