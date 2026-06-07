from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from videos.application.pipeline_context import PipelineContext

if TYPE_CHECKING:
    from videos.application.ports.artifact_store import ArtifactStore
    from videos.application.ports.layout_engine import LayoutEngine
    from videos.application.ports.renderer import Renderer
    from videos.application.ports.scene_builder import SceneBuilder
    from videos.application.ports.telemetry import Telemetry
    from videos.domain.storyboard import Storyboard

logger = logging.getLogger(__name__)


class FinalRenderStep:
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
        if context.quality != "final":
            return context
        if context.storyboard is None:
            return context

        renderer_context = (
            self._renderer.quality_context(context.quality)
            if hasattr(self._renderer, "quality_context")
            else contextlib.nullcontext()
        )
        with renderer_context:
            full_scene = self._build_full_storyboard(context.storyboard)
            final_path = self._artifact_store.resolve_output_path(
                context.concept_id, "final"
            )
            result = self._renderer.render(
                full_scene, final_path, quality="final"
            )

        if not result.success:
            raise RuntimeError(
                f"Final render failed for {context.concept_id!r}"
            )

        context.final_result = result
        return context

    def _build_full_storyboard(self, storyboard: Storyboard) -> object:
        if hasattr(self._scene_builder, "build_storyboard"):
            return self._scene_builder.build_storyboard(
                storyboard, self._layout_engine
            )
        return self._scene_builder.build(
            self._layout_engine.apply(storyboard.scenes[0])
        )
