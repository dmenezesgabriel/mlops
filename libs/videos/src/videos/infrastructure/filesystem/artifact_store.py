from __future__ import annotations

import logging
import shutil
from pathlib import Path

from videos.domain._base import require_slug

logger = logging.getLogger(__name__)


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

    def write_final(self, source_path: Path, concept_id: str) -> Path:
        dest = self._final_dir / self._concept_filename(concept_id)
        shutil.copy2(source_path, dest)
        logger.info(
            "Copied final artifact",
            extra={"concept_id": concept_id, "output_path": str(dest)},
        )
        return dest

    def write_preview(self, source_path: Path, concept_id: str) -> Path:
        dest = self._preview_dir / self._concept_filename(concept_id)
        shutil.copy2(source_path, dest)
        logger.info(
            "Copied preview artifact",
            extra={"concept_id": concept_id, "output_path": str(dest)},
        )
        return dest

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        if quality == "final":
            return self._final_dir / self._concept_filename(concept_id)
        return self._preview_dir / self._concept_filename(concept_id)

    def resolve_scene_preview_path(
        self, concept_id: str, scene_id: str
    ) -> Path:
        concept_slug = require_slug(concept_id, "concept_id")
        scene_slug = require_slug(scene_id, "scene_id")
        return self._scenes_dir / f"{concept_slug}_{scene_slug}.mp4"
