from __future__ import annotations

from pathlib import Path

import pytest

from videos.concepts.registry import ConceptRegistry
from videos.core.application.quality_gate import QualityGate
from videos.core.application.render_pipeline import RenderPipeline
from videos.core.application.storyboard_planner import StoryboardPlanner
from videos.core.domain.concept import ConceptId
from videos.core.ports.artifact_store import ArtifactStore
from videos.core.ports.layout_engine import LayoutEngine
from videos.core.ports.renderer import Renderer, RenderResult
from videos.core.ports.scene_builder import SceneBuilder
from videos.core.ports.telemetry import Telemetry
from videos.declarative.loader import load_concept_from_yaml_file

TEST_YAML_DIR = Path(__file__).parents[3] / "fixtures" / "concepts"


class StubRenderer(Renderer):
    def render(self, scene_job: object, output_path: Path) -> RenderResult:
        return RenderResult(
            output_path=output_path, duration_ms=100.0, success=True
        )


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
        self.errors: list[tuple[Exception, dict[str, object]]] = []

    def record_event(
        self, event_name: str, attributes: dict[str, object]
    ) -> None:
        self.events.append((event_name, attributes))

    def record_error(
        self, error: Exception, attributes: dict[str, object]
    ) -> None:
        self.errors.append((error, attributes))


class StubArtifactStore(ArtifactStore):
    def write_final(self, source_path: Path, concept_id: str) -> Path:
        return Path(f"{concept_id}_final.mp4")

    def write_preview(self, source_path: Path, concept_id: str) -> Path:
        return Path(f"{concept_id}_preview.mp4")

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        return Path(f"{concept_id}_{quality}.mp4")


class TestE2EYamlConcepts:
    def test_load_yaml_and_create_narrative(self) -> None:
        # Arrange
        path = TEST_YAML_DIR / "test_e2e.yaml"

        # Act
        ext = load_concept_from_yaml_file(str(path))

        # Assert
        assert ext.concept.id.value == "test_e2e"
        narrative = ext.create_narrative()
        assert len(narrative.beats) == 2
        assert narrative.beats[0].kind.value == "opening"
        assert narrative.beats[-1].kind.value == "recap"

    def test_plan_storyboard_from_yaml_concept(self) -> None:
        # Arrange
        path = TEST_YAML_DIR / "test_e2e.yaml"
        ext = load_concept_from_yaml_file(str(path))
        narrative = ext.create_narrative()
        planner = StoryboardPlanner()

        # Act
        storyboard = planner.plan(narrative)

        # Assert
        assert len(storyboard.scenes) == len(narrative.beats)
        assert storyboard.total_expected_duration == pytest.approx(
            narrative.total_duration
        )

    def test_quality_gate_passes_yaml_concept(self) -> None:
        # Arrange
        path = TEST_YAML_DIR / "test_e2e.yaml"
        ext = load_concept_from_yaml_file(str(path))
        narrative = ext.create_narrative()
        planner = StoryboardPlanner()
        storyboard = planner.plan(narrative)
        gate = QualityGate()

        # Act
        report = gate.validate(storyboard.scenes)

        # Assert
        assert report.passed, f"Quality gate failed: {report.violations}"

    def test_render_pipeline_with_yaml_concept(self) -> None:
        # Arrange
        path = TEST_YAML_DIR / "test_e2e.yaml"
        ext = load_concept_from_yaml_file(str(path))
        narrative = ext.create_narrative()
        planner = StoryboardPlanner()
        storyboard = planner.plan(narrative)
        pipeline = RenderPipeline(
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )

        # Act
        results = pipeline.execute(storyboard, "test_e2e")

        # Assert
        assert len(results) == len(narrative.beats)
        assert all(r.success for r in results)


class TestE2EDirector:
    def test_director_with_yaml_concept_fails_unknown(self) -> None:
        # Arrange
        from videos.core.application.director import Director

        director = Director(
            concept_id="nonexistent",
            renderer=StubRenderer(),
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=StubArtifactStore(),
            telemetry=StubTelemetry(),
        )

        # Act & Assert
        with pytest.raises(LookupError, match="Unknown concept"):
            director.produce()

    def test_register_yaml_and_director_finds_it(self) -> None:
        # Arrange
        ConceptRegistry._extensions.clear()
        path = TEST_YAML_DIR / "test_e2e.yaml"
        ext = load_concept_from_yaml_file(str(path))
        ConceptRegistry.register(ext)

        # Act
        retrieved = ConceptRegistry.get(ConceptId("test_e2e"))

        # Assert
        assert retrieved.concept.id.value == "test_e2e"


class TestE2ERegisterAll:
    def test_register_all_includes_yaml(self) -> None:
        # Arrange
        ConceptRegistry._extensions.clear()
        from videos.concepts import register_all

        # Act
        register_all(definitions_dir=TEST_YAML_DIR)

        # Assert
        ext = ConceptRegistry.get(ConceptId("test_e2e"))
        assert ext is not None
        narrative = ext.create_narrative()
        assert len(narrative.beats) > 0
