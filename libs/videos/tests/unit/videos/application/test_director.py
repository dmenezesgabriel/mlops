from __future__ import annotations

from pathlib import Path

import pytest
from videos.application.director import Director
from videos.application.pipeline_context import PipelineContext
from videos.application.production_pipeline import ProductionPipeline
from videos.domain.entities.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.domain.entities.concept_registry import ConceptRegistry
from videos.domain.entities.narrative import Narrative
from videos.domain.value_objects.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
)

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
    title = ConceptTitle(short="T", subtitle="")
    return Concept(
        id=ConceptId("test"),
        metadata=ConceptMetadata(title=title, description="", tags=()),
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


def _registry_with_test_concept(
    narrative: Narrative | None = None,
) -> ConceptRegistry:
    registry = ConceptRegistry()
    concept = _minimal_concept()
    registry.register(
        FixedConceptExtension(
            concept, narrative or _minimal_narrative(concept)
        )
    )
    return registry


class TestDirector:
    def test_director_produce_calls_renderer_for_each_scene(
        self, tmp_path: Path
    ) -> None:
        # Arrange
        registry = _registry_with_test_concept()
        renderer = StubRenderer()

        director = Director(
            concept_id="test",
            renderer=renderer,
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(tmp_path),
            telemetry=RecordingTelemetry(),
            linter_service=RecordingLinter(),
            concept_registry=registry,
        )

        # Act
        director.produce(quality="preview")

        # Assert
        # 2 beats = 2 render calls
        assert len(renderer.jobs) == 2
        # Verify unique paths for each scene
        paths = [job[1] for job in renderer.jobs]
        assert len(set(paths)) == 2
        assert all("test_beat_" in str(p) for p in paths)

    def test_director_fails_unknown_concept(self) -> None:
        # Arrange
        director = Director(
            concept_id="nonexistent",
            renderer=StubRenderer(),
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(Path("/tmp")),
            telemetry=RecordingTelemetry(),
            concept_registry=ConceptRegistry(),
        )

        # Act & Assert
        with pytest.raises(LookupError, match="Unknown concept"):
            director.produce()

    def test_director_rejects_unknown_quality(self) -> None:
        # Arrange
        renderer = StubRenderer()
        director = Director(
            concept_id="test",
            renderer=renderer,
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(Path("/tmp")),
            telemetry=RecordingTelemetry(),
            concept_registry=ConceptRegistry(),
        )

        # Act & Assert — must fail before any scene renders
        with pytest.raises(ValueError, match="quality"):
            director.produce(quality="bogus")
        assert renderer.jobs == []

    def test_director_produce_final_quality(self, tmp_path: Path) -> None:
        # Arrange
        registry = _registry_with_test_concept()
        artifact_store = StubArtifactStore(tmp_path)

        director = Director(
            concept_id="test",
            renderer=StubRenderer(),
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=artifact_store,
            telemetry=RecordingTelemetry(),
            linter_service=RecordingLinter(),
            concept_registry=registry,
        )

        # Act
        director.produce(quality="final")

        # Assert
        # Verify resolve_output_path was called with "final"
        assert ("test", "final") in artifact_store.output_calls

    def test_director_constructs_with_pipeline_only(self) -> None:
        # Arrange — an injected pipeline needs no adapters
        executed: list[PipelineContext] = []

        class _RecordingPipeline(ProductionPipeline):
            def __init__(self, sink: list[PipelineContext]) -> None:
                super().__init__(steps=())
                self._sink = sink

            def execute(self, context: PipelineContext) -> PipelineContext:
                self._sink.append(context)
                return context

        director = Director(
            concept_id="test", pipeline=_RecordingPipeline(executed)
        )

        # Act
        context = director.produce()

        # Assert
        assert executed == [context]
        assert context.concept_id == "test"

    def test_director_requires_pipeline_or_adapters(self) -> None:
        with pytest.raises(ValueError, match="missing: renderer"):
            Director(concept_id="test")

    def test_produce_returns_pipeline_context(self, tmp_path: Path) -> None:
        # Arrange — produce must hand back the context carrying final_result
        registry = _registry_with_test_concept()
        director = Director(
            concept_id="test",
            renderer=StubRenderer(),
            scene_builder=FakeSceneBuilder(),
            layout_engine=PassthroughLayoutEngine(),
            artifact_store=StubArtifactStore(tmp_path),
            telemetry=RecordingTelemetry(),
            linter_service=RecordingLinter(),
            concept_registry=registry,
        )

        # Act
        context = director.produce(quality="final")

        # Assert
        assert context.final_result is not None
        assert context.final_result.success
