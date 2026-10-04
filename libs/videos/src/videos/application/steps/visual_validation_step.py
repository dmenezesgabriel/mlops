from __future__ import annotations

import logging

from videos.application.pipeline_context import PipelineContext
from videos.application.ports.linter import Linter

logger = logging.getLogger(__name__)


class VisualValidationStep:
    def __init__(
        self,
        linter_service: Linter | None = None,
    ) -> None:
        self._linter_service = linter_service

    def execute(self, context: PipelineContext) -> PipelineContext:
        if self._linter_service is None:
            return context
        if context.scene_results is None:
            return context
        if context.storyboard is None:
            raise RuntimeError(
                "VisualValidationStep requires storyboard in context when "
                "scene results are present"
            )
        for scene, result in zip(
            context.storyboard.scenes, context.scene_results, strict=True
        ):
            image_path = result.output_path.with_suffix(".png")
            if not image_path.exists():
                raise RuntimeError(
                    f"Missing preview image for scene {scene.scene_id!r}: "
                    f"expected {image_path}"
                )
            self._linter_service.verify_visuals(image_path, scene.scene_id)
            if not result.output_path.exists():
                raise RuntimeError(
                    f"Missing rendered video for scene {scene.scene_id!r}: "
                    f"expected {result.output_path}"
                )
            self._linter_service.verify_video(
                result.output_path, scene.scene_id
            )
        return context
