from __future__ import annotations

import logging

from videos.application.pipeline_context import PipelineContext
from videos.application.ports.artifact_store import ArtifactStore
from videos.application.ports.layout_engine import LayoutEngine
from videos.application.ports.renderer import Renderer
from videos.application.ports.scene_builder import SceneBuilder
from videos.application.ports.telemetry import Telemetry

logger = logging.getLogger(__name__)


class PreviewRenderStep:
    def __init__(
        self,
        renderer: Renderer,
        scene_builder: SceneBuilder,
        layout_engine: LayoutEngine,
        artifact_store: ArtifactStore,
        telemetry: Telemetry,
    ) -> None:
        self._renderer = renderer
        self._scene_builder = scene_builder
        self._layout_engine = layout_engine
        self._artifact_store = artifact_store
        self._telemetry = telemetry

    def execute(self, context: PipelineContext) -> PipelineContext:
        if context.storyboard is None:
            raise RuntimeError(
                "PreviewRenderStep requires storyboard to be set in context"
            )
        results: list = []
        for index, scene_spec in enumerate(context.storyboard.scenes):
            positioned = self._layout_engine.apply(scene_spec)
            built_scene = self._scene_builder.build(positioned)

            scene_id = f"beat_{index}"
            output_path = self._artifact_store.resolve_scene_preview_path(
                context.concept_id, scene_id
            )
            result = self._renderer.render(
                built_scene, output_path, quality="preview"
            )

            if not result.success:
                raise RuntimeError(
                    f"Renderer failed for scene {scene_spec.scene_id!r}."
                )

            self._telemetry.record_event(
                "scene_rendered",
                {
                    "concept_id": context.concept_id,
                    "scene_id": scene_spec.scene_id,
                    "correlation_id": context.correlation_id,
                    "duration_ms": result.duration_ms,
                    "output_path": str(result.output_path),
                },
            )
            results.append(result)

        context.scene_results = results
        return context
