from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import SceneSpec, VisualObject
from videos.core.domain.timeline import TimelineEvent, TimelineSpec
from videos.validation.timeline_rules import TimelineRules


def _scene(
    visual_objects: tuple[VisualObject, ...] = (),
    timeline: TimelineSpec | None = None,
) -> SceneSpec:
    return SceneSpec(
        scene_id="test_scene",
        title="Test",
        goal="Test goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        visual_objects=visual_objects,
        timeline=timeline,
    )


class TestTimelineRules:
    def test_passes_missing_timeline(self) -> None:
        rules = TimelineRules()
        scene = _scene()
        violations = rules.validate(scene)
        assert len(violations) == 0

    def test_passes_valid_timeline(self) -> None:
        rules = TimelineRules()
        scene = _scene(
            visual_objects=(
                VisualObject(object_id="o1", region="title", semantic_purpose="Display"),
            ),
            timeline=TimelineSpec(
                events=(TimelineEvent(time_seconds=0.0, action="appear", target_object_id="o1"),)
            ),
        )
        violations = rules.validate(scene)
        assert len(violations) == 0

    def test_fails_missing_target(self) -> None:
        rules = TimelineRules()
        scene = _scene(
            timeline=TimelineSpec(
                events=(
                    TimelineEvent(
                        time_seconds=0.0,
                        action="appear",
                        target_object_id="nonexistent",
                    ),
                )
            ),
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "timeline_target_must_exist"

    def test_fails_event_exceeds_duration(self) -> None:
        rules = TimelineRules()
        scene = _scene(
            visual_objects=(
                VisualObject(object_id="o1", region="title", semantic_purpose="Display"),
            ),
            timeline=TimelineSpec(
                events=(TimelineEvent(time_seconds=10.0, action="appear", target_object_id="o1"),)
            ),
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "timeline_event_exceeds_duration"
