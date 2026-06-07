from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from videos.core.application.pipeline_context import PipelineContext
from videos.core.application.production_pipeline import ProductionPipeline
from videos.core.application.steps.final_render_step import FinalRenderStep
from videos.core.application.steps.narrative_planning_step import (
    NarrativePlanningStep,
)
from videos.core.application.steps.preview_render_step import PreviewRenderStep
from videos.core.application.steps.static_validation_step import (
    StaticValidationStep,
)
from videos.core.application.steps.visual_validation_step import (
    VisualValidationStep,
)
from videos.core.ports.artifact_store import ArtifactStore
from videos.core.ports.layout_engine import LayoutEngine
from videos.core.ports.renderer import Renderer
from videos.core.ports.scene_builder import SceneBuilder
from videos.core.ports.telemetry import Telemetry
from videos.validation.linter_service import LinterService

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Director:
    def __init__(
        self,
        concept_id: str,
        renderer: Renderer,
        scene_builder: SceneBuilder,
        layout_engine: LayoutEngine,
        artifact_store: ArtifactStore,
        telemetry: Telemetry,
        linter_service: LinterService | None = None,
        pipeline: ProductionPipeline | None = None,
    ) -> None:
        self._concept_id = concept_id
        self._pipeline = pipeline or self._build_default_pipeline(
            renderer=renderer,
            scene_builder=scene_builder,
            layout_engine=layout_engine,
            artifact_store=artifact_store,
            telemetry=telemetry,
            linter_service=linter_service or LinterService(),
        )

    def produce(self, quality: str = "preview") -> None:
        context = PipelineContext(concept_id=self._concept_id, quality=quality)
        self._pipeline.execute(context)

    @staticmethod
    def _build_default_pipeline(
        renderer: Renderer,
        scene_builder: SceneBuilder,
        layout_engine: LayoutEngine,
        artifact_store: ArtifactStore,
        telemetry: Telemetry,
        linter_service: LinterService,
    ) -> ProductionPipeline:
        return ProductionPipeline(
            steps=[
                NarrativePlanningStep(),
                StaticValidationStep(),
                PreviewRenderStep(
                    renderer=renderer,
                    scene_builder=scene_builder,
                    layout_engine=layout_engine,
                    artifact_store=artifact_store,
                    telemetry=telemetry,
                ),
                VisualValidationStep(linter_service=linter_service),
                FinalRenderStep(
                    renderer=renderer,
                    scene_builder=scene_builder,
                    layout_engine=layout_engine,
                    artifact_store=artifact_store,
                    telemetry=telemetry,
                ),
            ]
        )
