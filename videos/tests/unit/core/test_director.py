from pathlib import Path

import pytest
from mlops_videos.core._application._director import SceneDirector
from mlops_videos.core._domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from mlops_videos.core._domain._narrative import Beat, BeatKind, NarrationLine, Narrative
from mlops_videos.core.ports._renderer import VideoRenderer
from mlops_videos.core.ports._scene_builder import SceneBuilder, ScenePlan


def _minimal_concept() -> Concept:
    title = ConceptTitle(short="T", subtitle="")
    return Concept(id=ConceptId("test"), metadata=ConceptMetadata(title=title, description="", tags=()))


def _minimal_narrative(concept: Concept | None = None) -> Narrative:
    c = concept or _minimal_concept()
    return Narrative(c, (
        Beat(BeatKind.OPENING, NarrationLine("start", 10.0), "open", {}),
        Beat(BeatKind.REVEAL, NarrationLine("mid", 10.0), "mid", {}),
        Beat(BeatKind.REVEAL, NarrationLine("mid2", 10.0), "mid2", {}),
        Beat(BeatKind.RECAP, NarrationLine("end", 10.0), "close", {}),
    ))


class StubBuilder(SceneBuilder):
    def __init__(self) -> None:
        self.planned: list[Narrative] = []

    def plan(self, narrative: Narrative) -> ScenePlan:
        self.planned.append(narrative)
        return ScenePlan(narrative=narrative)


class StubRenderer(VideoRenderer):
    def __init__(self) -> None:
        self.rendered: list[ScenePlan] = []

    def render(self, plan: ScenePlan, output_path: Path) -> Path:
        self.rendered.append(plan)
        return output_path


class DummyExtension:
    def __init__(self, concept: Concept | None = None) -> None:
        self._concept = concept or _minimal_concept()

    @property
    def concept(self) -> Concept:
        return self._concept

    def create_narrative(self) -> Narrative:
        return _minimal_narrative(self._concept)


def test_produce_calls_builder_and_renderer(tmp_path: Path) -> None:
    builder = StubBuilder()
    renderer = StubRenderer()
    director = SceneDirector(builder=builder, renderer=renderer)
    provider = DummyExtension()

    output = director.produce(provider=provider, output_path=tmp_path / "out.mp4")

    assert len(builder.planned) == 1
    assert len(renderer.rendered) == 1
    assert output == tmp_path / "out.mp4"


def test_produce_does_not_error_for_reasonable_duration(tmp_path: Path) -> None:
    builder = StubBuilder()
    renderer = StubRenderer()
    director = SceneDirector(builder=builder, renderer=renderer)
    provider = DummyExtension()

    director.produce(provider=provider, output_path=tmp_path / "out.mp4")

    assert builder.planned[0].total_duration == 40.0  # narrative directly


def test_produce_rejects_out_of_range_duration(tmp_path: Path) -> None:
    title = ConceptTitle(short="T", subtitle="")
    concept = Concept(id=ConceptId("long"), metadata=ConceptMetadata(title=title, description="", tags=()))
    beats = tuple(
        Beat(BeatKind.REVEAL, NarrationLine("x", 12.0), "x", {})
        for _ in range(11)
    )
    narrative = Narrative(concept=concept, beats=(
        Beat(BeatKind.OPENING, NarrationLine("open", 2.0), "open", {}),
        *beats,
        Beat(BeatKind.RECAP, NarrationLine("end", 2.0), "close", {}),
    ))

    class LongNarrativeProvider:
        def create_narrative(self) -> Narrative:
            return narrative

    builder = StubBuilder()
    renderer = StubRenderer()
    director = SceneDirector(builder=builder, renderer=renderer)

    with pytest.raises(ValueError, match="duration"):
        director.produce(provider=LongNarrativeProvider(), output_path=tmp_path / "out.mp4")
