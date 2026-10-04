"""Named fakes for the application ports (ADR-0005).

Shared across the unit and integration suites so a port seam is faked one
way everywhere — each fake records what the pipeline did rather than
standing in as an ad-hoc attribute bag.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

from videos.application.ports.artifact_store import ArtifactStore
from videos.application.ports.layout_engine import LayoutEngine
from videos.application.ports.linter import Linter
from videos.application.ports.renderer import Renderer, RenderResult
from videos.application.ports.scene_builder import SceneBuilder
from videos.application.ports.telemetry import Telemetry
from videos.domain.entities.concept import Concept
from videos.domain.entities.concept_extension import ConceptExtension
from videos.domain.entities.narrative import Narrative
from videos.domain.entities.storyboard import Storyboard
from videos.domain.value_objects.scene_spec import SceneSpec


class RecordingTelemetry(Telemetry):
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def record_event(
        self, event_name: str, attributes: dict[str, object]
    ) -> None:
        self.events.append((event_name, attributes))


class StubRenderer(Renderer):
    """Records render jobs and writes the mp4 + sibling png artifacts the
    validation seam checks for. `log` optionally shares ordering with
    other fakes driven in the same call chain."""

    def __init__(self, log: list[str] | None = None) -> None:
        self.log = log if log is not None else []
        self.jobs: list[tuple[object, Path, str]] = []

    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        self.log.append(f"enter_context_{quality}")
        try:
            yield
        finally:
            self.log.append(f"exit_context_{quality}")

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        self.log.append("render_call")
        self.jobs.append((scene_job, output_path, quality))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.with_suffix(".png").touch()
        output_path.touch()
        return RenderResult(
            output_path=output_path, duration_ms=100.0, success=True
        )


class FailingRenderer(Renderer):
    """Always reports an unsuccessful render — no artifact claim."""

    @contextlib.contextmanager
    def quality_context(self, quality: str) -> Iterator[None]:
        yield

    def render(
        self, scene_job: object, output_path: Path, quality: str = "preview"
    ) -> RenderResult:
        return RenderResult(
            output_path=output_path, duration_ms=0.0, success=False
        )


class FakeSceneBuilder(SceneBuilder):
    """Returns opaque scene objects; `log` optionally records ordering."""

    def __init__(self, log: list[str] | None = None) -> None:
        self._log = log
        self.built: list[object] = []

    def build(self, scene_spec: SceneSpec) -> object:
        if self._log is not None:
            self._log.append("build_scene")
        self.built.append(scene_spec)
        return object()

    def build_storyboard(
        self, storyboard: Storyboard, layout_engine: LayoutEngine
    ) -> object:
        if self._log is not None:
            self._log.append("build_storyboard")
        return object()


class PassthroughLayoutEngine(LayoutEngine):
    def apply(self, scene: SceneSpec) -> SceneSpec:
        return scene


class StubArtifactStore(ArtifactStore):
    """Resolves artifact paths under a caller-owned root and records the
    resolve calls so tests can assert which path was requested."""

    def __init__(self, output_root: Path) -> None:
        self._output_root = output_root
        self.output_calls: list[tuple[str, str]] = []
        self.preview_calls: list[tuple[str, str]] = []

    def resolve_output_path(self, concept_id: str, quality: str) -> Path:
        self.output_calls.append((concept_id, quality))
        return self._output_root / f"{concept_id}_{quality}.mp4"

    def resolve_scene_preview_path(
        self, concept_id: str, scene_id: str
    ) -> Path:
        self.preview_calls.append((concept_id, scene_id))
        return self._output_root / f"{concept_id}_{scene_id}.mp4"


class RecordingLinter(Linter):
    def __init__(self) -> None:
        self.visual_calls: list[tuple[Path, str]] = []
        self.video_calls: list[tuple[Path, str]] = []

    def verify_visuals(self, image_path: Path, scene_id: str) -> None:
        self.visual_calls.append((image_path, scene_id))

    def verify_video(self, video_path: Path, scene_id: str) -> None:
        self.video_calls.append((video_path, scene_id))


class FixedConceptExtension(ConceptExtension):
    """A registered concept with a canned narrative."""

    def __init__(self, concept: Concept, narrative: Narrative) -> None:
        self._concept = concept
        self._narrative = narrative

    @property
    def concept(self) -> Concept:
        return self._concept

    def create_narrative(self) -> Narrative:
        return self._narrative
