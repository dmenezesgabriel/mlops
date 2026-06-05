from pathlib import Path

import pytest
from videos.core.application._render_pipeline import RenderPipeline
from videos.core.domain._layout import LayoutRegion, LayoutSpec
from videos.core.domain._scene_spec import SceneSpec
from videos.core.domain._storyboard import Storyboard
from videos.core.ports._artifact_store import ArtifactStore
from videos.core.ports._layout_engine import LayoutEngine
from videos.core.ports._renderer import Renderer, RenderResult
from videos.core.ports._scene_builder import SceneBuilder
from videos.core.ports._telemetry import Telemetry


class StubRenderer(Renderer):
    def render(self, scene_job: object, output_path: Path) -> RenderResult:
        return RenderResult(output_path=output_path, duration_ms=100.0, success=True)


class StubSceneBuilder(SceneBuilder):
    def build(self, scene_spec: object) -> object:
        return object()


class StubLayoutEngine(LayoutEngine):
    def apply(self, scene: object) -> object:
        return scene

    def validate_placement(self, layout: object) -> list[str]:
        return []


class StubTelemetry(Telemetry):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def record_event(self, event_name: str, attributes: dict[str, object]) -> None:
        self.events.append((event_name, attributes))

    def record_error(self, error: Exception, attributes: dict[str, object]) -> None:
        pass


class StubArtifactStore(ArtifactStore):
    def write_final(self, source_path: Path, concept_id: str) -> Path:
        return Path(f"/tmp/{concept_id}_final.mp4")

    def write_preview(self, source_path: Path, concept_id: str) -> Path:
        return Path(f"/tmp/{concept_id}_preview.mp4")

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        return Path(f"/tmp/{concept_id}_{quality}.mp4")


def _storyboard() -> Storyboard:
    scene = SceneSpec(
        scene_id="s1",
        title="Test",
        goal="Test goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
    )
    return Storyboard(scenes=[scene])


class TestRenderPipeline:
    def test_execute_renders_scenes(self) -> None:
        pipeline = RenderPipeline(
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )
        results = pipeline.execute(_storyboard(), "test_concept")
        assert len(results) == 1
        assert results[0].success

    def test_execute_rejects_empty_storyboard(self) -> None:
        pipeline = RenderPipeline(
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )
        with pytest.raises(ValueError):
            pipeline.execute(Storyboard(scenes=[]), "test")
