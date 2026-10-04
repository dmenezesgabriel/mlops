from __future__ import annotations

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
from videos.domain.entities.concept_registry import ConceptRegistry


class Director:
    def __init__(
        self,
        concept_id: str,
        renderer: Renderer | None = None,
        scene_builder: SceneBuilder | None = None,
        layout_engine: LayoutEngine | None = None,
        artifact_store: ArtifactStore | None = None,
        telemetry: Telemetry | None = None,
        concept_registry: ConceptRegistry | None = None,
        linter_service: Linter | None = None,
        pipeline: ProductionPipeline | None = None,
    ) -> None:
        self._concept_id = concept_id
        if pipeline is not None:
            self._pipeline = pipeline
            return
        if (
            renderer is None
            or scene_builder is None
            or layout_engine is None
            or artifact_store is None
            or telemetry is None
            or concept_registry is None
        ):
            missing = ", ".join(
                name
                for name, adapter in (
                    ("renderer", renderer),
                    ("scene_builder", scene_builder),
                    ("layout_engine", layout_engine),
                    ("artifact_store", artifact_store),
                    ("telemetry", telemetry),
                    ("concept_registry", concept_registry),
                )
                if adapter is None
            )
            raise ValueError(
                f"Director requires 'pipeline' or all adapters; "
                f"missing: {missing}"
            )
        self._pipeline = self._build_default_pipeline(
            renderer=renderer,
            scene_builder=scene_builder,
            layout_engine=layout_engine,
            artifact_store=artifact_store,
            telemetry=telemetry,
            linter_service=linter_service,
            concept_registry=concept_registry,
        )

    def produce(self, quality: str = "preview") -> PipelineContext:
        context = PipelineContext(concept_id=self._concept_id, quality=quality)
        return self._pipeline.execute(context)

    @staticmethod
    def _build_default_pipeline(
        renderer: Renderer,
        scene_builder: SceneBuilder,
        layout_engine: LayoutEngine,
        artifact_store: ArtifactStore,
        telemetry: Telemetry,
        linter_service: Linter | None,
        concept_registry: ConceptRegistry,
    ) -> ProductionPipeline:
        return ProductionPipeline(
            steps=[
                NarrativePlanningStep(registry=concept_registry),
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
