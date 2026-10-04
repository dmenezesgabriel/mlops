from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from tests._fakes import (
    FailingRenderer,
    FakeSceneBuilder,
    PassthroughLayoutEngine,
    RecordingTelemetry,
    StubArtifactStore,
    StubRenderer,
)
from videos.application.pipeline_context import PipelineContext
from videos.application.ports.artifact_store import ArtifactStore
from videos.application.ports.layout_engine import LayoutEngine
from videos.application.ports.scene_builder import SceneBuilder
from videos.application.steps.final_render_step import FinalRenderStep
from videos.application.steps.preview_render_step import PreviewRenderStep
from videos.domain.entities.storyboard import Storyboard
from videos.domain.value_objects.layout import LayoutRegion, LayoutSpec
from videos.domain.value_objects.scene_spec import SceneSpec


def _one_scene_storyboard() -> Storyboard:
    scene = SceneSpec(
        scene_id="s1",
        title="Title",
        goal="Goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
    )
    return Storyboard(scenes=(scene,))


def _context(quality: str) -> PipelineContext:
    context = PipelineContext(concept_id="test", quality=quality)
    context.storyboard = _one_scene_storyboard()
    return context


class BuildOnlySceneBuilder:
    """Structural fake missing the port-declared build_storyboard."""

    def build(self, scene_spec: object) -> object:
        return object()


class PartialSceneBuilder(SceneBuilder):
    """Inherits the port but provides no real build_storyboard — the
    port-level NotImplementedError contract, made explicit."""

    def build(self, scene_spec: SceneSpec) -> object:
        return object()

    def build_storyboard(
        self, storyboard: Storyboard, layout_engine: LayoutEngine
    ) -> object:
        raise NotImplementedError


class PartialArtifactStore(ArtifactStore):
    """Inherits the port but provides no real resolve_scene_preview_path —
    the port-level NotImplementedError contract, made explicit."""

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        return Path(f"{concept_id}_{quality}.mp4")

    def resolve_scene_preview_path(
        self, concept_id: str, scene_id: str
    ) -> Path:
        raise NotImplementedError


def test_preview_render_step_enters_quality_context(tmp_path: Path) -> None:
    log: list[str] = []
    step = PreviewRenderStep(
        renderer=StubRenderer(log=log),
        scene_builder=FakeSceneBuilder(log=log),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(tmp_path),
        telemetry=RecordingTelemetry(),
    )

    step.execute(_context(quality="preview"))

    assert log == [
        "enter_context_preview",
        "build_scene",
        "render_call",
        "exit_context_preview",
    ]


def test_final_render_step_enters_quality_context(tmp_path: Path) -> None:
    log: list[str] = []
    step = FinalRenderStep(
        renderer=StubRenderer(log=log),
        scene_builder=FakeSceneBuilder(log=log),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(tmp_path),
        telemetry=RecordingTelemetry(),
    )

    step.execute(_context(quality="final"))

    assert log == [
        "enter_context_final",
        "build_storyboard",
        "render_call",
        "exit_context_final",
    ]


def test_preview_step_enters_preview_context_on_final_run(
    tmp_path: Path,
) -> None:
    log: list[str] = []
    step = PreviewRenderStep(
        renderer=StubRenderer(log=log),
        scene_builder=FakeSceneBuilder(log=log),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(tmp_path),
        telemetry=RecordingTelemetry(),
    )

    step.execute(_context(quality="final"))

    assert "enter_context_preview" in log
    assert "enter_context_final" not in log


def test_preview_step_requires_storyboard() -> None:
    step = PreviewRenderStep(
        renderer=StubRenderer(),
        scene_builder=FakeSceneBuilder(),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(Path("/tmp")),
        telemetry=RecordingTelemetry(),
    )

    with pytest.raises(RuntimeError, match="requires storyboard"):
        step.execute(PipelineContext(concept_id="test"))


def test_preview_step_raises_on_failed_render(tmp_path: Path) -> None:
    step = PreviewRenderStep(
        renderer=FailingRenderer(),
        scene_builder=FakeSceneBuilder(),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(tmp_path),
        telemetry=RecordingTelemetry(),
    )

    with pytest.raises(RuntimeError, match="Renderer failed"):
        step.execute(_context(quality="preview"))


def test_final_step_skips_when_final_run_has_no_storyboard() -> None:
    step = FinalRenderStep(
        renderer=StubRenderer(),
        scene_builder=FakeSceneBuilder(),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(Path("/tmp")),
        telemetry=RecordingTelemetry(),
    )

    context = PipelineContext(concept_id="test", quality="final")
    result = step.execute(context)

    assert result is context
    assert result.final_result is None


def test_final_step_raises_on_failed_render(tmp_path: Path) -> None:
    step = FinalRenderStep(
        renderer=FailingRenderer(),
        scene_builder=FakeSceneBuilder(),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(tmp_path),
        telemetry=RecordingTelemetry(),
    )

    with pytest.raises(RuntimeError, match="Final render failed"):
        step.execute(_context(quality="final"))


def test_final_step_raises_on_builder_without_build_storyboard() -> None:
    step = FinalRenderStep(
        renderer=StubRenderer(),
        scene_builder=cast(SceneBuilder, BuildOnlySceneBuilder()),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(Path("/tmp")),
        telemetry=RecordingTelemetry(),
    )

    with pytest.raises(AttributeError):
        step.execute(_context(quality="final"))


def test_final_step_propagates_unimplemented_storyboard_build() -> None:
    step = FinalRenderStep(
        renderer=StubRenderer(),
        scene_builder=PartialSceneBuilder(),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=StubArtifactStore(Path("/tmp")),
        telemetry=RecordingTelemetry(),
    )

    with pytest.raises(NotImplementedError):
        step.execute(_context(quality="final"))


def test_preview_step_propagates_unimplemented_preview_path() -> None:
    step = PreviewRenderStep(
        renderer=StubRenderer(),
        scene_builder=FakeSceneBuilder(),
        layout_engine=PassthroughLayoutEngine(),
        artifact_store=PartialArtifactStore(),
        telemetry=RecordingTelemetry(),
    )

    with pytest.raises(NotImplementedError):
        step.execute(_context(quality="preview"))
