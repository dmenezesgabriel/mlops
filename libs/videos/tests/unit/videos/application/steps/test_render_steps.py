from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import MagicMock

from videos.application.pipeline_context import PipelineContext
from videos.application.steps.final_render_step import FinalRenderStep
from videos.application.steps.preview_render_step import PreviewRenderStep
from videos.domain.layout import LayoutRegion, LayoutSpec
from videos.domain.scene_spec import SceneSpec
from videos.domain.storyboard import Storyboard


class SpyRenderer:
    def __init__(self) -> None:
        self.log: list[str] = []
        self.context_calls = 0

    @contextlib.contextmanager
    def quality_context(
        self, quality: str
    ) -> contextlib.AbstractContextManager[None]:
        self.log.append(f"enter_context_{quality}")
        self.context_calls += 1
        try:
            yield
        finally:
            self.log.append(f"exit_context_{quality}")

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> MagicMock:
        self.log.append("render_call")
        mock_res = MagicMock()
        mock_res.success = True
        mock_res.output_path = output_path
        mock_res.duration_ms = 50.0
        return mock_res


def test_preview_render_step_enters_quality_context() -> None:
    renderer = SpyRenderer()
    scene_builder = MagicMock()
    scene_builder.build.side_effect = lambda spec: (
        renderer.log.append("build_scene") or object()
    )

    layout_engine = MagicMock()
    layout_engine.apply.side_effect = lambda spec: spec

    artifact_store = MagicMock()
    artifact_store.resolve_scene_preview_path.return_value = Path("scene.mp4")

    telemetry = MagicMock()

    step = PreviewRenderStep(
        renderer=renderer,
        scene_builder=scene_builder,
        layout_engine=layout_engine,
        artifact_store=artifact_store,
        telemetry=telemetry,
    )

    scene = SceneSpec(
        scene_id="s1",
        title="Title",
        goal="Goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
    )
    context = PipelineContext(concept_id="test", quality="preview")
    context.storyboard = Storyboard(scenes=[scene])

    step.execute(context)

    assert renderer.log == [
        "enter_context_preview",
        "build_scene",
        "render_call",
        "exit_context_preview",
    ]


def test_final_render_step_enters_quality_context() -> None:
    renderer = SpyRenderer()
    scene_builder = MagicMock()
    scene_builder.build_storyboard.side_effect = lambda sb, le: (
        renderer.log.append("build_storyboard") or object()
    )

    layout_engine = MagicMock()
    artifact_store = MagicMock()
    artifact_store.resolve_output_path.return_value = Path("final.mp4")

    telemetry = MagicMock()

    step = FinalRenderStep(
        renderer=renderer,
        scene_builder=scene_builder,
        layout_engine=layout_engine,
        artifact_store=artifact_store,
        telemetry=telemetry,
    )

    scene = SceneSpec(
        scene_id="s1",
        title="Title",
        goal="Goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
    )
    context = PipelineContext(concept_id="test", quality="final")
    context.storyboard = Storyboard(scenes=[scene])

    step.execute(context)

    assert renderer.log == [
        "enter_context_final",
        "build_storyboard",
        "render_call",
        "exit_context_final",
    ]
