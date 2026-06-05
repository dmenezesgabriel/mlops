from pathlib import Path

import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.adapters.manim.layout_engine import ManimLayoutEngine  # noqa: E402
from videos.adapters.manim.scene_builder import ManimSceneBuilder  # noqa: E402
from videos.core.application.render_pipeline import RenderPipeline  # noqa: E402
from videos.core.domain.layout import LayoutRegion, LayoutSpec  # noqa: E402
from videos.core.domain.scene_spec import SceneSpec  # noqa: E402
from videos.core.domain.storyboard import Storyboard  # noqa: E402
from videos.core.ports.artifact_store import ArtifactStore  # noqa: E402
from videos.core.ports.renderer import Renderer, RenderResult  # noqa: E402
from videos.core.ports.telemetry import Telemetry  # noqa: E402


class StubRenderer(Renderer):
    def render(self, scene_job: object, output_path: Path) -> RenderResult:
        return RenderResult(output_path=output_path, duration_ms=50.0, success=True)


class StubTelemetry(Telemetry):
    def record_event(self, event_name: str, attributes: dict[str, object]) -> None:
        pass

    def record_error(self, error: Exception, attributes: dict[str, object]) -> None:
        pass


class StubArtifactStore(ArtifactStore):
    def write_final(self, source_path: Path, concept_id: str) -> Path:
        return Path(f"{concept_id}_final.mp4")

    def write_preview(self, source_path: Path, concept_id: str) -> Path:
        return Path(f"{concept_id}_preview.mp4")

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        return Path(f"{concept_id}_{quality}.mp4")


class TestRenderPipelineIntegration:
    def test_execute_with_real_components(self) -> None:
        pipeline = RenderPipeline(
            renderer=StubRenderer(),
            scene_builder=ManimSceneBuilder(),
            layout_engine=ManimLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )
        scene = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Test goal",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        storyboard = Storyboard(scenes=[scene])
        results = pipeline.execute(storyboard, "test_concept")
        assert len(results) == 1
        assert results[0].success
