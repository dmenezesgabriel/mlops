from __future__ import annotations

import logging
import shutil
from pathlib import Path

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

    def write_final(self, source_path: Path, concept_id: str) -> Path:
        dest = self._final_dir / f"{concept_id}.mp4"
        shutil.copy2(source_path, dest)
        logger.info(
            "Copied final artifact",
            extra={"concept_id": concept_id, "output_path": str(dest)},
        )
        return dest

    def write_preview(self, source_path: Path, concept_id: str) -> Path:
        dest = self._preview_dir / f"{concept_id}.mp4"
        shutil.copy2(source_path, dest)
        logger.info(
            "Copied preview artifact",
            extra={"concept_id": concept_id, "output_path": str(dest)},
        )
        return dest

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        if quality == "final":
            return self._final_dir / f"{concept_id}.mp4"
        return self._preview_dir / f"{concept_id}.mp4"

    def resolve_scene_preview_path(self, concept_id: str, scene_id: str) -> Path:
        return self._scenes_dir / f"{concept_id}_{scene_id}.mp4"
