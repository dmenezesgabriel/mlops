from __future__ import annotations

import logging

from videos.concepts._registry import ConceptRegistry
from videos.core.domain._concept import ConceptId
from videos.core.ports._artifact_store import ArtifactStore
from videos.core.ports._layout_engine import LayoutEngine
from videos.core.ports._renderer import Renderer
from videos.core.ports._scene_builder import SceneBuilder
from videos.core.ports._telemetry import Telemetry

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
    ) -> None:
        self._concept_id = concept_id
        self._renderer = renderer
        self._scene_builder = scene_builder
        self._layout_engine = layout_engine
        self._artifact_store = artifact_store
        self._telemetry = telemetry

    def produce(self) -> None:
        correlation_id = f"{self._concept_id}_{id(self)}"
        self._telemetry.record_event(
            "render_started",
            {"concept_id": self._concept_id, "correlation_id": correlation_id},
        )

        extension = ConceptRegistry.get(ConceptId(self._concept_id))
        narrative = extension.create_narrative()

        storyboard_planner = self._get_planner()
        storyboard = storyboard_planner.plan(narrative)

        scene_compiler = self._get_compiler()
        scene_specs = scene_compiler.compile(storyboard)

        quality_gate = self._get_quality_gate()
        report = quality_gate.validate(scene_specs)
        if not report.passed:
            self._telemetry.record_error(
                ValueError("Quality gate failed"),
                {
                    "concept_id": self._concept_id,
                    "correlation_id": correlation_id,
                    "violations": [str(v) for v in report.violations],
                },
            )
            msg = "\n".join(f"  [{v.rule}] {v.suggestion}" for v in report.violations)
            raise RuntimeError(f"Quality gate rejected {self._concept_id!r}:\n{msg}")

        for scene_spec in scene_specs:
            positioned = self._layout_engine.apply(scene_spec)
            built_scene = self._scene_builder.build(positioned)

            output_path = self._artifact_store.resolve_output_path(self._concept_id, "preview")
            result = self._renderer.render(built_scene, output_path)

            self._telemetry.record_event(
                "scene_rendered",
                {
                    "concept_id": self._concept_id,
                    "scene_id": scene_spec.scene_id,
                    "correlation_id": correlation_id,
                    "duration_ms": result.duration_ms,
                    "output_path": str(result.output_path),
                },
            )

        self._telemetry.record_event(
            "render_completed",
            {"concept_id": self._concept_id, "correlation_id": correlation_id},
        )

    @staticmethod
    def _get_planner() -> object:
        from videos.core.application._storyboard_planner import StoryboardPlanner

        return StoryboardPlanner()

    @staticmethod
    def _get_compiler() -> object:
        from videos.core.application._scene_compiler import SceneCompiler

        return SceneCompiler()

    @staticmethod
    def _get_quality_gate() -> object:
        from videos.core.application._quality_gate import QualityGate

        return QualityGate()
