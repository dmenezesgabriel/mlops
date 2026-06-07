from __future__ import annotations

import logging
from collections.abc import Sequence

from videos.application.pipeline_context import PipelineContext
from videos.application.ports.pipeline_step import PipelineStep

logger = logging.getLogger(__name__)


class ProductionPipeline:
    def __init__(self, steps: Sequence[PipelineStep]) -> None:
        self._steps = list(steps)

    def execute(self, context: PipelineContext) -> PipelineContext:
        current = context
        for step in self._steps:
            current = step.execute(current)
        return current
