from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from videos.application.pipeline_context import PipelineContext
from videos.application.ports.artifact_store import ArtifactStore
from videos.application.ports.layout_engine import LayoutEngine
from videos.application.ports.linter import Linter
from videos.application.ports.renderer import Renderer
from videos.application.ports.scene_builder import SceneBuilder
from videos.application.ports.telemetry import Telemetry
from videos.application.production_pipeline import ProductionPipeline
from videos.application.steps.final_render_step import FinalRenderStep
from videos.application.steps.narrative_planning_step import (
    NarrativePlanningStep,
)
from videos.application.steps.preview_render_step import PreviewRenderStep
from videos.application.steps.static_validation_step import (
    StaticValidationStep,
)
from videos.application.steps.visual_validation_step import (
    VisualValidationStep,
)

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
        linter_service: Linter | None = None,
        pipeline: ProductionPipeline | None = None,
    ) -> None:
        self._concept_id = concept_id
        self._pipeline = pipeline or self._build_default_pipeline(
            renderer=renderer,
            scene_builder=scene_builder,
            layout_engine=layout_engine,
            artifact_store=artifact_store,
            telemetry=telemetry,
            linter_service=linter_service,
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
        linter_service: Linter | None,
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
