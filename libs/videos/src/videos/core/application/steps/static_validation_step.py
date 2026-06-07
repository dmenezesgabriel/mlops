from __future__ import annotations

import logging

from videos.core.application.pipeline_context import PipelineContext
from videos.core.application.quality_gate import QualityGate
from videos.core.application.storyboard_planner import StoryboardPlanner

logger = logging.getLogger(__name__)


class StaticValidationStep:
    def __init__(
        self,
        quality_gate: QualityGate | None = None,
        planner: StoryboardPlanner | None = None,
    ) -> None:
        self._quality_gate = quality_gate or QualityGate()
        self._planner = planner or StoryboardPlanner()

    def execute(self, context: PipelineContext) -> PipelineContext:
        if context.narrative is None:
            raise RuntimeError(
                "StaticValidationStep requires narrative to be set in context"
            )
        storyboard = self._planner.plan(context.narrative)
        report = self._quality_gate.validate(storyboard.scenes)

        if not report.passed:
            details = "; ".join(
                f"{v.rule}: {v.suggestion}" for v in report.violations
            )
            raise RuntimeError(
                f"Quality gate rejected {context.concept_id!r}: {details}"
            )

        context.storyboard = storyboard
        context.quality_report = report
        return context
