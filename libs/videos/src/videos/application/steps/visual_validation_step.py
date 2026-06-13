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
        for result in context.scene_results:
            image_path = result.output_path.with_suffix(".png")
            if image_path.exists():
                self._linter_service.verify_visuals(image_path, "unknown")
            if result.output_path.exists():
                self._linter_service.verify_video(
                    result.output_path, "unknown"
                )
        return context
