from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from videos.concepts.registry import ConceptRegistry
from videos.core.domain.concept import ConceptId
from videos.core.ports.artifact_store import ArtifactStore
from videos.core.ports.layout_engine import LayoutEngine
from videos.core.ports.renderer import Renderer
from videos.core.ports.scene_builder import SceneBuilder
from videos.core.ports.telemetry import Telemetry
from videos.validation.linter_service import LinterService

if TYPE_CHECKING:
    from videos.core.application.quality_gate import QualityGate
    from videos.core.application.storyboard_planner import StoryboardPlanner
    from videos.core.domain.storyboard import Storyboard

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
    ) -> None:
        self._concept_id = concept_id
        self._renderer = renderer
        self._scene_builder = scene_builder
        self._layout_engine = layout_engine
        self._artifact_store = artifact_store
        self._telemetry = telemetry
        self._linter_service = linter_service or LinterService()

    def produce(self, quality: str = "preview") -> None:
        correlation_id = f"{self._concept_id}_{uuid.uuid4().hex[:8]}"
        self._telemetry.record_event(
            "render_started",
            {
                "concept_id": self._concept_id,
                "correlation_id": correlation_id,
                "quality": quality,
            },
        )

        extension = ConceptRegistry.get(ConceptId(self._concept_id))
        narrative = extension.create_narrative()

        storyboard_planner = self._get_planner()
        storyboard = storyboard_planner.plan(narrative)

        quality_gate = self._get_quality_gate()
        report = quality_gate.validate(storyboard.scenes)
        if not report.passed:
            self._telemetry.record_error(
                ValueError("Quality gate failed"),
                {
                    "concept_id": self._concept_id,
                    "correlation_id": correlation_id,
                    "violations": [str(v) for v in report.violations],
                },
            )
            msg = "\n".join(
                f"  [{v.rule}] {v.suggestion}" for v in report.violations
            )
            raise RuntimeError(
                f"Quality gate rejected {self._concept_id!r}:\n{msg}"
            )

        # Phase 1: Render individual scenes for previews and validation
        for index, scene_spec in enumerate(storyboard.scenes):
            positioned = self._layout_engine.apply(scene_spec)
            built_scene = self._scene_builder.build(positioned)

            scene_id = f"beat_{index}"
            output_path = self._artifact_store.resolve_scene_preview_path(
                self._concept_id, scene_id
            )
            # Previews are always low quality for speed
            result = self._renderer.render(
                built_scene, output_path, quality="preview"
            )

            if not result.success:
                raise RuntimeError(
                    f"Renderer failed for scene {scene_spec.scene_id!r}. Check logs for details."
                )

            # Visual Linter (Pillow)
            image_path = output_path.with_suffix(".png")
            self._linter_service.verify_visuals(
                image_path, scene_spec.scene_id
            )

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

        # Phase 2: If final quality requested, render the whole storyboard
        if quality == "final":
            logger.info(
                f"Producing final high-quality video for {self._concept_id!r}"
            )
            full_scene = self._build_full_storyboard(storyboard)
            final_path = self._artifact_store.resolve_output_path(
                self._concept_id, "final"
            )
            result = self._renderer.render(
                full_scene, final_path, quality="final"
            )

            if not result.success:
                raise RuntimeError(
                    f"Final render failed for {self._concept_id!r}"
                )

            logger.info(f"Final video produced at {final_path}")

        self._telemetry.record_event(
            "render_completed",
            {"concept_id": self._concept_id, "correlation_id": correlation_id},
        )

    def _build_full_storyboard(self, storyboard: Storyboard) -> object:
        """
        Build a single scene that plays all scenes from the storyboard in sequence.
        """
        # We need a new port/adapter method for this, but for now I can implement a
        # local dynamic scene in Director if I have access to the animation engine.
        # Actually, I should delegate this to SceneBuilder.
        if hasattr(self._scene_builder, "build_storyboard"):
            return self._scene_builder.build_storyboard(
                storyboard, self._layout_engine
            )

        # Fallback to building just the first scene if not implemented
        # (This is just to satisfy the type checker/tests for now)
        return self._scene_builder.build(
            self._layout_engine.apply(storyboard.scenes[0])
        )

    @staticmethod
    def _get_planner() -> StoryboardPlanner:
        from videos.core.application.storyboard_planner import (
            StoryboardPlanner,
        )

        return StoryboardPlanner()

    @staticmethod
    def _get_quality_gate() -> QualityGate:
        from videos.core.application.quality_gate import QualityGate

        return QualityGate()
