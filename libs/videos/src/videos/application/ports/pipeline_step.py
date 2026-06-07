from __future__ import annotations

from typing import Protocol

from videos.application.pipeline_context import PipelineContext


class PipelineStep(Protocol):
    def execute(self, context: PipelineContext) -> PipelineContext: ...
