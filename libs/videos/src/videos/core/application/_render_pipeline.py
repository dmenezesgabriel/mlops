from __future__ import annotations

import logging
from collections.abc import Sequence

from videos.core.application._quality_gate import QualityGate
from videos.core.domain._scene_spec import SceneSpec
from videos.core.domain._storyboard import Storyboard
from videos.core.ports._artifact_store import ArtifactStore
from videos.core.ports._layout_engine import LayoutEngine
from videos.core.ports._renderer import Renderer, RenderResult
from videos.core.ports._scene_builder import SceneBuilder
from videos.core.ports._telemetry import Telemetry

logger = logging.getLogger(__name__)


class RenderPipeline:
    def __init__(
        self,
        renderer: Renderer,
        scene_builder: SceneBuilder,
        layout_engine: LayoutEngine,
        artifact_store: ArtifactStore,
        telemetry: Telemetry,
        quality_gate: QualityGate | None = None,
    ) -> None:
        self._renderer = renderer
        self._scene_builder = scene_builder
        self._layout_engine = layout_engine
        self._artifact_store = artifact_store
        self._telemetry = telemetry
        self._quality_gate = quality_gate or QualityGate()

    def execute(
        self,
        storyboard: Storyboard,
        concept_id: str,
        quality: str = "preview",
    ) -> list[RenderResult]:
        correlation_id = f"{concept_id}_{id(self)}"

        scenes = self._compile_storyboard(storyboard)
        report = self._quality_gate.validate(scenes)

        if not report.passed:
            details = "; ".join(f"{v.rule}: {v.suggestion}" for v in report.violations)
            raise RuntimeError(f"Quality gate rejected {concept_id!r}: {details}")

        results: list[RenderResult] = []
        for scene_spec in scenes:
            positioned = self._layout_engine.apply(scene_spec)
            built_scene = self._scene_builder.build(positioned)

            output_path = self._artifact_store.resolve_output_path(concept_id, quality)
            result = self._renderer.render(built_scene, output_path)

            self._telemetry.record_event(
                "scene_rendered",
                {
                    "concept_id": concept_id,
                    "scene_id": scene_spec.scene_id,
                    "correlation_id": correlation_id,
                    "duration_ms": result.duration_ms,
                    "output_path": str(result.output_path),
                },
            )
            results.append(result)

        return results

    @staticmethod
    def _compile_storyboard(storyboard: Storyboard) -> Sequence[SceneSpec]:
        return storyboard.scenes
