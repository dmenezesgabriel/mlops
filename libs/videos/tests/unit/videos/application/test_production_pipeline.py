from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest
from videos.application.pipeline_context import PipelineContext
from videos.application.ports.artifact_store import ArtifactStore
from videos.application.ports.layout_engine import LayoutEngine
from videos.application.ports.renderer import RenderResult
from videos.application.ports.scene_builder import SceneBuilder
from videos.application.ports.telemetry import Telemetry
from videos.application.production_pipeline import ProductionPipeline
from videos.application.quality_gate import QualityGate
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
from videos.domain.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.domain.concept_registry import ConceptRegistry
from videos.domain.layout import LayoutRegion, LayoutSpec
from videos.domain.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
    Narrative,
)
from videos.domain.quality import RuleViolation
from videos.domain.scene_spec import SceneSpec
from videos.domain.storyboard import Storyboard


def _minimal_concept() -> Concept:
    return Concept(
        id=ConceptId("test"),
        metadata=ConceptMetadata(
            title=ConceptTitle(short="T", subtitle=""),
            description="",
            tags=(),
        ),
    )


def _minimal_narrative(concept: Concept | None = None) -> Narrative:
    c = concept or _minimal_concept()
    return Narrative(
        c,
        (
            Beat(BeatKind.OPENING, NarrationLine("start", 5.0), "open", {}),
            Beat(BeatKind.RECAP, NarrationLine("end", 5.0), "close", {}),
        ),
    )


class StubTelemetry(Telemetry):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def record_event(
        self, event_name: str, attributes: dict[str, object]
    ) -> None:
        self.events.append((event_name, attributes))

    def record_error(
        self, error: Exception, attributes: dict[str, object]
    ) -> None:
        pass


class StubRenderer:
    def __init__(self) -> None:
        self.jobs: list = []

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        self.jobs.append((scene_job, output_path, quality))
        png_path = output_path.with_suffix(".png")
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.touch()
        return RenderResult(
            output_path=output_path, duration_ms=100.0, success=True
        )


class StubSceneBuilder(SceneBuilder):
    def build(self, scene_spec: object) -> object:
        return object()

    def build_storyboard(
        self, storyboard: object, layout_engine: object
    ) -> object:
        return object()


class StubLayoutEngine(LayoutEngine):
    def apply(self, scene: object) -> SceneSpec:
        return cast(SceneSpec, scene)

    def validate_placement(self, layout: object) -> list[str]:
        return []


class StubArtifactStore(ArtifactStore):
    def __init__(self) -> None:
        self._tmp = Path("/tmp")

    def write_final(self, source_path: Path, concept_id: str) -> Path:
        return self._tmp / f"{concept_id}_final.mp4"

    def write_preview(self, source_path: Path, concept_id: str) -> Path:
        return self._tmp / f"{concept_id}_preview.mp4"

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        return self._tmp / f"{concept_id}_{quality}.mp4"

    def resolve_scene_preview_path(
        self, concept_id: str, scene_id: str
    ) -> Path:
        return self._tmp / f"{concept_id}_{scene_id}.mp4"


class TestNarrativePlanningStep:
    def test_plans_narrative_from_registry(self, tmp_path: Path) -> None:
        ConceptRegistry._extensions.clear()
        narrative = _minimal_narrative()
        mock_ext = MagicMock()
        mock_ext.concept = _minimal_concept()
        mock_ext.create_narrative.return_value = narrative
        ConceptRegistry.register(mock_ext)

        step = NarrativePlanningStep()
        ctx = PipelineContext(concept_id="test")
        result = step.execute(ctx)

        assert result.narrative is not None
        assert result.narrative.total_duration == 10.0
        assert result.correlation_id != ""

    def test_fails_on_unknown_concept(self) -> None:
        ConceptRegistry._extensions.clear()
        step = NarrativePlanningStep()
        ctx = PipelineContext(concept_id="nonexistent")
        with pytest.raises(LookupError, match="Unknown concept"):
            step.execute(ctx)


class TestStaticValidationStep:
    def test_passes_valid_storyboard(self) -> None:
        narrative = _minimal_narrative()
        ctx = PipelineContext(concept_id="test")
        ctx.narrative = narrative
        ctx.correlation_id = "test_123"

        step = StaticValidationStep()
        result = step.execute(ctx)
        assert result.quality_report is not None
        assert result.quality_report.passed
        assert result.storyboard is not None

    def test_fails_on_custom_validator(self) -> None:
        def always_fail(scene: SceneSpec) -> list[RuleViolation]:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="custom_fail",
                    suggestion="Always fails",
                )
            ]

        gate = QualityGate(static_rules=[always_fail])
        narrative = _minimal_narrative()
        ctx = PipelineContext(concept_id="test")
        ctx.narrative = narrative
        ctx.correlation_id = "test_123"

        step = StaticValidationStep(quality_gate=gate)
        with pytest.raises(RuntimeError, match="Quality gate rejected"):
            step.execute(ctx)


class TestPreviewRenderStep:
    def test_renders_all_scenes(self, tmp_path: Path) -> None:
        scene = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Goal",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        storyboard = Storyboard(scenes=[scene])
        ctx = PipelineContext(concept_id="test", correlation_id="test_123")
        ctx.storyboard = storyboard

        renderer = StubRenderer()
        store = StubArtifactStore()
        store._tmp = tmp_path

        step = PreviewRenderStep(
            renderer=renderer,
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=store,
            telemetry=StubTelemetry(),
        )
        result = step.execute(ctx)
        assert result.scene_results is not None
        assert len(result.scene_results) == 1
        assert result.scene_results[0].success


class TestFinalRenderStep:
    def test_renders_full_storyboard_when_final(self, tmp_path: Path) -> None:
        scene = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Goal",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        storyboard = Storyboard(scenes=[scene])
        ctx = PipelineContext(
            concept_id="test",
            quality="final",
            correlation_id="test_123",
        )
        ctx.storyboard = storyboard

        renderer = StubRenderer()
        store = StubArtifactStore()
        store._tmp = tmp_path

        step = FinalRenderStep(
            renderer=renderer,
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=store,
            telemetry=StubTelemetry(),
        )
        result = step.execute(ctx)
        assert result.final_result is not None
        assert result.final_result.success

    def test_skips_when_preview(self) -> None:
        ctx = PipelineContext(
            concept_id="test",
            quality="preview",
            correlation_id="test_123",
        )
        step = FinalRenderStep(
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )
        result = step.execute(ctx)
        assert result.final_result is None


class TestProductionPipeline:
    def test_executes_steps_in_order(self) -> None:
        events = []

        @dataclass
        class Step:
            name: str

            def execute(self, ctx: PipelineContext) -> PipelineContext:
                events.append(self.name)
                return ctx

        pipeline = ProductionPipeline(steps=[Step("a"), Step("b"), Step("c")])
        ctx = PipelineContext(concept_id="test")
        pipeline.execute(ctx)
        assert events == ["a", "b", "c"]

    def test_stops_on_failure(self) -> None:
        @dataclass
        class FailStep:
            def execute(self, ctx: PipelineContext) -> PipelineContext:
                msg = "Step failed"
                raise RuntimeError(msg)

        @dataclass
        class NeverReached:
            def execute(self, ctx: PipelineContext) -> PipelineContext:
                pytest.fail("Should not be reached")

        pipeline = ProductionPipeline(steps=[FailStep(), NeverReached()])
        ctx = PipelineContext(concept_id="test")
        with pytest.raises(RuntimeError, match="Step failed"):
            pipeline.execute(ctx)


class TestVisualValidationStep:
    def test_skips_when_no_scene_results(self) -> None:
        step = VisualValidationStep(linter_service=MagicMock())
        ctx = PipelineContext(concept_id="test", correlation_id="test_123")
        result = step.execute(ctx)
        assert result is ctx  # no-op
