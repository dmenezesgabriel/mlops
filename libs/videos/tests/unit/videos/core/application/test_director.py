from pathlib import Path

import pytest
from videos.core.application._director import Director
from videos.core.domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain._narrative import Beat, BeatKind, NarrationLine, Narrative
from videos.core.ports._artifact_store import ArtifactStore
from videos.core.ports._layout_engine import LayoutEngine
from videos.core.ports._renderer import Renderer, RenderResult
from videos.core.ports._scene_builder import SceneBuilder
from videos.core.ports._telemetry import Telemetry


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
        self.jobs: list[tuple[object, Path]] = []

    def render(self, scene_job: object, output_path: Path) -> RenderResult:
        self.jobs.append((scene_job, output_path))
        return RenderResult(output_path=output_path, duration_ms=100.0, success=True)


class StubSceneBuilder(SceneBuilder):
    def __init__(self) -> None:
        self.specs: list = []

    def build(self, scene_spec: object) -> object:
        self.specs.append(scene_spec)
        return object()


class StubLayoutEngine(LayoutEngine):
    def apply(self, scene: object) -> object:
        return scene

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


def test_director_produce_calls_renderer() -> None:
    telemetry = StubTelemetry()
    renderer = StubRenderer()
    scene_builder = StubSceneBuilder()
    layout_engine = StubLayoutEngine()
    artifact_store = StubArtifactStore()

    director = Director(
        concept_id="test",
        renderer=renderer,
        scene_builder=scene_builder,
        layout_engine=layout_engine,
        artifact_store=artifact_store,
        telemetry=telemetry,
    )

    with pytest.raises(LookupError, match="Unknown concept"):
        director.produce()
