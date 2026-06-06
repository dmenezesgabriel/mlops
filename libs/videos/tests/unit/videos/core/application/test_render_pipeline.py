from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

import pytest

from videos.core.application.render_pipeline import RenderPipeline
from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import SceneSpec
from videos.core.domain.storyboard import Storyboard
from videos.core.ports.artifact_store import ArtifactStore
from videos.core.ports.layout_engine import LayoutEngine
from videos.core.ports.renderer import Renderer, RenderResult
from videos.core.ports.scene_builder import SceneBuilder
from videos.core.ports.telemetry import Telemetry


class StubRenderer(Renderer):
    def render(self, scene_job: object, output_path: Path) -> RenderResult:
        return RenderResult(
            output_path=output_path, duration_ms=100.0, success=True
        )


class StubSceneBuilder(SceneBuilder):
    def build(self, scene_spec: object) -> object:
        return object()


class StubLayoutEngine(LayoutEngine):
    def apply(self, scene: object) -> SceneSpec:
        return cast(SceneSpec, scene)

    def validate_placement(self, layout: object) -> list[str]:
        return []


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

    def test_execute_uses_uuid_correlation_id(self) -> None:
        telemetry = StubTelemetry()
        pipeline = RenderPipeline(
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=telemetry,
        )
        pipeline.execute(_storyboard(), "test_concept")
        correlation_ids = [
            attrs.get("correlation_id", "")
            for _, attrs in telemetry.events
            if "correlation_id" in attrs
        ]
        assert len(correlation_ids) > 0
        for cid in correlation_ids:
            assert isinstance(cid, str)
            assert cid.startswith("test_concept_")
            hex_part = cid.split("_")[-1]
            assert len(hex_part) == 8
            int(hex_part, 16)  # raises ValueError if not hex

    def test_execute_with_executor_renders_all_scenes(self) -> None:
        pipeline = RenderPipeline(
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )
        scene2 = SceneSpec(
            scene_id="s2",
            title="Test2",
            goal="Goal2",
            duration_seconds=3.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        sb = Storyboard(scenes=[_storyboard().scenes[0], scene2])
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = pipeline.execute(sb, "test_concept", executor=executor)
        assert len(results) == 2
        assert all(r.success for r in results)

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
