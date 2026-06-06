from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from concurrent.futures import Executor
from typing import TYPE_CHECKING

from videos.core.application.quality_gate import QualityGate
from videos.core.domain.scene_spec import SceneSpec
from videos.core.domain.storyboard import Storyboard
from videos.core.ports.artifact_store import ArtifactStore
from videos.core.ports.layout_engine import LayoutEngine
from videos.core.ports.renderer import Renderer, RenderResult
from videos.core.ports.scene_builder import SceneBuilder
from videos.core.ports.telemetry import Telemetry

if TYPE_CHECKING:
    from concurrent.futures import Future

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
        executor: Executor | None = None,
    ) -> list[RenderResult]:
        correlation_id = f"{concept_id}_{uuid.uuid4().hex[:8]}"

        scenes = self._compile_storyboard(storyboard)
        report = self._quality_gate.validate(scenes)

        if not report.passed:
            details = "; ".join(
                f"{v.rule}: {v.suggestion}" for v in report.violations
            )
            raise RuntimeError(
                f"Quality gate rejected {concept_id!r}: {details}"
            )

        if executor is not None:
            return self._execute_parallel(
                scenes, concept_id, quality, correlation_id, executor
            )
        return self._execute_sequential(
            scenes, concept_id, quality, correlation_id
        )

    def _render_one_scene(
        self,
        scene_spec: SceneSpec,
        concept_id: str,
        quality: str,
        correlation_id: str,
    ) -> RenderResult:
        positioned = self._layout_engine.apply(scene_spec)
        built_scene = self._scene_builder.build(positioned)
        output_path = self._artifact_store.resolve_output_path(
            concept_id, quality
        )
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
        return result

    def _execute_sequential(
        self,
        scenes: Sequence[SceneSpec],
        concept_id: str,
        quality: str,
        correlation_id: str,
    ) -> list[RenderResult]:
        results: list[RenderResult] = []
        for scene_spec in scenes:
            results.append(
                self._render_one_scene(
                    scene_spec, concept_id, quality, correlation_id
                )
            )
        return results

    def _execute_parallel(
        self,
        scenes: Sequence[SceneSpec],
        concept_id: str,
        quality: str,
        correlation_id: str,
        executor: Executor,
    ) -> list[RenderResult]:
        futures: list[Future[RenderResult]] = [
            executor.submit(
                self._render_one_scene, s, concept_id, quality, correlation_id
            )
            for s in scenes
        ]
        return [f.result() for f in futures]

    @staticmethod
    def _compile_storyboard(storyboard: Storyboard) -> Sequence[SceneSpec]:
        return storyboard.scenes
