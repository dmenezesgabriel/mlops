from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from videos.application.pipeline_context import PipelineContext
from videos.application.ports.renderer import RenderResult
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
from videos.application.use_cases.quality_gate import QualityGate
from videos.domain.entities.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.domain.entities.concept_registry import ConceptRegistry
from videos.domain.entities.narrative import Narrative
from videos.domain.entities.storyboard import Storyboard
from videos.domain.value_objects.layout import LayoutRegion, LayoutSpec
from videos.domain.value_objects.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
)
from videos.domain.value_objects.quality import RuleViolation
from videos.domain.value_objects.scene_spec import SceneSpec

from tests._fakes import (
    FakeSceneBuilder,
    FixedConceptExtension,
    PassthroughLayoutEngine,
    RecordingLinter,
    RecordingTelemetry,
    StubArtifactStore,
    StubRenderer,
)


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


def _registered_ext() -> FixedConceptExtension:
    return FixedConceptExtension(_minimal_concept(), _minimal_narrative())


class TestNarrativePlanningStep:
    def test_plans_narrative_from_registry(self, tmp_path: Path) -> None:
        registry = ConceptRegistry()
        registry.register(_registered_ext())

        step = NarrativePlanningStep(registry)
        ctx = PipelineContext(concept_id="test")
        result = step.execute(ctx)

        assert result.narrative is not None
        assert (
            sum(b.narration.duration_seconds for b in result.narrative.beats)
            == 10.0
        )
        assert result.correlation_id != ""

    def test_reads_only_the_injected_registry(self) -> None:
        # The step must resolve against its own registry instance, not any
        # ambient registrations (the ClassVar singleton leaked across tests).
        populated = ConceptRegistry()
        populated.register(_registered_ext())
        empty = ConceptRegistry()

        with pytest.raises(LookupError, match="Unknown concept"):
            NarrativePlanningStep(empty).execute(
                PipelineContext(concept_id="test")
            )
        result = NarrativePlanningStep(populated).execute(
            PipelineContext(concept_id="test")
        )
        assert result.narrative is not None

    def test_fails_on_unknown_concept(self) -> None:
        step = NarrativePlanningStep(ConceptRegistry())
        ctx = PipelineContext(concept_id="nonexistent")
        with pytest.raises(LookupError, match="Unknown concept"):
            step.execute(ctx)

    def test_rejects_narrative_for_other_concept(self) -> None:
        registry = ConceptRegistry()
        other = Concept(
            id=ConceptId("other"),
            metadata=ConceptMetadata(
                title=ConceptTitle(short="O", subtitle=""),
                description="",
                tags=(),
            ),
        )
        registry.register(
            FixedConceptExtension(
                _minimal_concept(), _minimal_narrative(concept=other)
            )
        )

        step = NarrativePlanningStep(registry)
        ctx = PipelineContext(concept_id="test")
        with pytest.raises(RuntimeError, match="other"):
            step.execute(ctx)

    def test_preserves_correlation_id(self) -> None:
        # The context owns correlation-id generation; a step must not
        # overwrite an id the caller already set.
        registry = ConceptRegistry()
        registry.register(_registered_ext())

        ctx = PipelineContext(concept_id="test", correlation_id="test_123")
        result = NarrativePlanningStep(registry).execute(ctx)

        assert result.correlation_id == "test_123"


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

    def test_requires_narrative(self) -> None:
        ctx = PipelineContext(concept_id="test")
        with pytest.raises(RuntimeError, match="requires narrative"):
            StaticValidationStep().execute(ctx)

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
        storyboard = Storyboard(scenes=(scene,))
        ctx = PipelineContext(concept_id="test", correlation_id="test_123")
        ctx.storyboard = storyboard

        step = PreviewRenderStep(
            renderer=StubRenderer(),
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(tmp_path),
            telemetry=RecordingTelemetry(),
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
        storyboard = Storyboard(scenes=(scene,))
        ctx = PipelineContext(
            concept_id="test",
            quality="final",
            correlation_id="test_123",
        )
        ctx.storyboard = storyboard

        step = FinalRenderStep(
            renderer=StubRenderer(),
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(tmp_path),
            telemetry=RecordingTelemetry(),
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
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(Path("/tmp")),
            telemetry=RecordingTelemetry(),
        )
        result = step.execute(ctx)
        assert result.final_result is None


class TestProductionPipeline:
    def test_executes_steps_in_order(self) -> None:
        events: list[str] = []

        @dataclass
        class Step:
            name: str

            def execute(self, context: PipelineContext) -> PipelineContext:
                events.append(self.name)
                return context

        pipeline = ProductionPipeline(steps=[Step("a"), Step("b"), Step("c")])
        ctx = PipelineContext(concept_id="test")
        pipeline.execute(ctx)
        assert events == ["a", "b", "c"]

    def test_stops_on_failure(self) -> None:
        @dataclass
        class FailStep:
            def execute(self, context: PipelineContext) -> PipelineContext:
                msg = "Step failed"
                raise RuntimeError(msg)

        @dataclass
        class NeverReached:
            def execute(self, context: PipelineContext) -> PipelineContext:
                pytest.fail("Should not be reached")

        pipeline = ProductionPipeline(steps=[FailStep(), NeverReached()])
        ctx = PipelineContext(concept_id="test")
        with pytest.raises(RuntimeError, match="Step failed"):
            pipeline.execute(ctx)


class TestVisualValidationStep:
    def _context_with_rendered_scene(
        self, tmp_path: Path, scene_id: str = "beat_0"
    ) -> PipelineContext:
        scene = SceneSpec(
            scene_id=scene_id,
            title="T",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        ctx = PipelineContext(concept_id="test", correlation_id="c")
        ctx.storyboard = Storyboard(scenes=(scene,))
        output_path = tmp_path / f"{scene_id}.mp4"
        ctx.scene_results = [
            RenderResult(
                output_path=output_path, duration_ms=1.0, success=True
            )
        ]
        return ctx

    def test_noop_without_linter(self, tmp_path: Path) -> None:
        # No linter configured: the step must return early without touching
        # the filesystem, even when results and a storyboard are present.
        ctx = self._context_with_rendered_scene(tmp_path)
        result = VisualValidationStep(linter_service=None).execute(ctx)
        assert result is ctx

    def test_skips_when_no_scene_results(self) -> None:
        step = VisualValidationStep(linter_service=RecordingLinter())
        ctx = PipelineContext(concept_id="test", correlation_id="test_123")
        result = step.execute(ctx)
        assert result is ctx  # no-op

    def test_verifies_artifacts_with_real_scene_ids(
        self, tmp_path: Path
    ) -> None:
        ctx = self._context_with_rendered_scene(tmp_path)
        assert ctx.scene_results is not None
        result_path = ctx.scene_results[0].output_path
        result_path.touch()
        result_path.with_suffix(".png").touch()
        linter = RecordingLinter()

        VisualValidationStep(linter_service=linter).execute(ctx)

        png_path = result_path.with_suffix(".png")
        assert linter.visual_calls == [(png_path, "beat_0")]
        assert linter.video_calls == [(result_path, "beat_0")]

    def test_raises_on_missing_preview_image(self, tmp_path: Path) -> None:
        ctx = self._context_with_rendered_scene(tmp_path)
        assert ctx.scene_results is not None
        ctx.scene_results[0].output_path.touch()
        linter = RecordingLinter()

        with pytest.raises(RuntimeError, match="beat_0"):
            VisualValidationStep(linter_service=linter).execute(ctx)

    def test_raises_on_missing_video(self, tmp_path: Path) -> None:
        ctx = self._context_with_rendered_scene(tmp_path)
        assert ctx.scene_results is not None
        ctx.scene_results[0].output_path.with_suffix(".png").touch()
        linter = RecordingLinter()

        with pytest.raises(RuntimeError, match="beat_0"):
            VisualValidationStep(linter_service=linter).execute(ctx)

    def test_requires_storyboard_when_results_present(
        self, tmp_path: Path
    ) -> None:
        ctx = PipelineContext(concept_id="test")
        output_path = tmp_path / "beat_0.mp4"
        output_path.touch()
        ctx.scene_results = [
            RenderResult(
                output_path=output_path, duration_ms=1.0, success=True
            )
        ]

        with pytest.raises(RuntimeError, match="storyboard"):
            VisualValidationStep(linter_service=RecordingLinter()).execute(ctx)
