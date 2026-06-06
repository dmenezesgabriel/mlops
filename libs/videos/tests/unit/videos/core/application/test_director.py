from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from videos.concepts.registry import ConceptRegistry
from videos.core.application.director import Director
from videos.core.domain.concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain.narrative import Beat, BeatKind, NarrationLine, Narrative
from videos.core.domain.scene_spec import SceneSpec
from videos.core.ports.artifact_store import ArtifactStore
from videos.core.ports.layout_engine import LayoutEngine
from videos.core.ports.renderer import Renderer, RenderResult
from videos.core.ports.scene_builder import SceneBuilder
from videos.core.ports.telemetry import Telemetry


def _minimal_concept() -> Concept:
    title = ConceptTitle(short="T", subtitle="")
    return Concept(
        id=ConceptId("test"), metadata=ConceptMetadata(title=title, description="", tags=())
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
        self.errors: list[tuple[Exception, dict[str, object]]] = []

    def record_event(self, event_name: str, attributes: dict[str, object]) -> None:
        self.events.append((event_name, attributes))

    def record_error(self, error: Exception, attributes: dict[str, object]) -> None:
        self.errors.append((error, attributes))


class StubRenderer(Renderer):
    def __init__(self) -> None:
        self.jobs: list[tuple[object, Path, str]] = []

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        self.jobs.append((scene_job, output_path, quality))
        # Create dummy PNG for linter
        png_path = output_path.with_suffix(".png")
        png_path.touch()
        return RenderResult(output_path=output_path, duration_ms=100.0, success=True)


class StubSceneBuilder(SceneBuilder):
    def __init__(self) -> None:
        self.specs: list = []

    def build(self, scene_spec: object) -> object:
        self.specs.append(scene_spec)
        return object()

    def build_storyboard(self, storyboard: object, layout_engine: object) -> object:
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

    def resolve_scene_preview_path(self, concept_id: str, scene_id: str) -> Path:
        return self._tmp / f"{concept_id}_{scene_id}.mp4"


class TestDirector:
    def test_director_produce_calls_renderer_for_each_scene(self, tmp_path: Path) -> None:
        # Arrange
        ConceptRegistry._extensions.clear()
        concept = _minimal_concept()
        narrative = _minimal_narrative(concept)

        mock_extension = MagicMock()
        mock_extension.concept = concept
        mock_extension.create_narrative.return_value = narrative
        ConceptRegistry.register(mock_extension)

        renderer = StubRenderer()
        artifact_store = StubArtifactStore()
        artifact_store._tmp = tmp_path

        director = Director(
            concept_id="test",
            renderer=renderer,
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=artifact_store,
            telemetry=StubTelemetry(),
            linter_service=MagicMock(),
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
        ConceptRegistry._extensions.clear()
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

    def test_director_produce_final_quality(self, tmp_path: Path) -> None:
        # Arrange
        ConceptRegistry._extensions.clear()
        concept = _minimal_concept()
        narrative = _minimal_narrative(concept)

        mock_extension = MagicMock()
        mock_extension.concept = concept
        mock_extension.create_narrative.return_value = narrative
        ConceptRegistry.register(mock_extension)

        renderer = StubRenderer()
        artifact_store = MagicMock(spec=ArtifactStore)
        artifact_store.resolve_output_path.return_value = tmp_path / "final.mp4"
        artifact_store.resolve_scene_preview_path.return_value = tmp_path / "scene.mp4"

        director = Director(
            concept_id="test",
            renderer=renderer,
            scene_builder=StubSceneBuilder(),
            layout_engine=StubLayoutEngine(),
            artifact_store=artifact_store,
            telemetry=StubTelemetry(),
            linter_service=MagicMock(),
        )

        # Act
        director.produce(quality="final")

        # Assert
        # Verify resolve_output_path was called with "final"
        artifact_store.resolve_output_path.assert_any_call("test", "final")
