import pytest
from videos.core.application._storyboard_planner import StoryboardPlanner
from videos.core.domain._concept import Concept, ConceptId, ConceptMetadata, ConceptTitle
from videos.core.domain._narrative import Beat, BeatKind, NarrationLine, Narrative


def _concept() -> Concept:
    return Concept(
        id=ConceptId("test_concept"),
        metadata=ConceptMetadata(
            title=ConceptTitle(short="Test", subtitle=""),
            description="",
            tags=(),
        ),
    )


def _narrative() -> Narrative:
    return Narrative(
        _concept(),
        (
            Beat(BeatKind.OPENING, NarrationLine("Open", 5.0), "open", {}),
            Beat(BeatKind.REVEAL, NarrationLine("Content", 4.0), "content", {}),
            Beat(BeatKind.RECAP, NarrationLine("End", 3.0), "end", {}),
        ),
    )


class TestStoryboardPlanner:
    def test_plan_creates_storyboard(self) -> None:
        planner = StoryboardPlanner()
        sb = planner.plan(_narrative())
        assert len(sb.scenes) == 3

    def test_scene_ids_match_narrative(self) -> None:
        planner = StoryboardPlanner()
        sb = planner.plan(_narrative())
        for scene in sb.scenes:
            assert scene.scene_id.startswith("test_concept")

    def test_duration_matches_narrative(self) -> None:
        planner = StoryboardPlanner()
        narrative = _narrative()
        sb = planner.plan(narrative)
        assert sb.total_expected_duration == pytest.approx(narrative.total_duration)
