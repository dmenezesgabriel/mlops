import pytest

from videos.core.application.storyboard_planner import StoryboardPlanner
from videos.core.domain.concept import (
    Concept,
    ConceptId,
    ConceptMetadata,
    ConceptTitle,
)
from videos.core.domain.narrative import (
    Beat,
    BeatKind,
    NarrationLine,
    Narrative,
)


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
            Beat(
                BeatKind.REVEAL, NarrationLine("Content", 4.0), "content", {}
            ),
            Beat(BeatKind.RECAP, NarrationLine("End", 3.0), "end", {}),
        ),
    )


class TestStoryboardPlanner:
    def test_plan_creates_storyboard(self) -> None:
        # Arrange
        planner = StoryboardPlanner()
        narrative = _narrative()

        # Act
        sb = planner.plan(narrative)

        # Assert
        assert len(sb.scenes) == 3

    def test_scene_ids_match_narrative(self) -> None:
        # Arrange
        planner = StoryboardPlanner()
        narrative = _narrative()

        # Act
        sb = planner.plan(narrative)

        # Assert
        for scene in sb.scenes:
            assert scene.scene_id.startswith("test_concept")

    def test_duration_matches_narrative(self) -> None:
        # Arrange
        planner = StoryboardPlanner()
        narrative = _narrative()

        # Act
        sb = planner.plan(narrative)

        # Assert
        assert sb.total_expected_duration == pytest.approx(
            narrative.total_duration
        )

    def test_plan_populates_components(self) -> None:
        # Arrange
        planner = StoryboardPlanner()
        narrative = _narrative()

        # Act
        sb = planner.plan(narrative)

        # Assert
        for scene in sb.scenes:
            assert len(scene.components) > 0
            # Each scene should at least have a title component
            assert any(c.type == "title" for c in scene.components)
