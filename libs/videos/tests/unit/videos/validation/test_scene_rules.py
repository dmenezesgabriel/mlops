from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import SceneSpec
from videos.validation.scene_rules import SceneRules


def _scene(
    scene_id: str = "s1",
    title: str = "Test",
    goal: str = "Goal",
    duration: float = 5.0,
) -> SceneSpec:
    return SceneSpec(
        scene_id=scene_id,
        title=title,
        goal=goal,
        duration_seconds=duration,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
    )


class TestSceneRules:
    def test_passes_valid_scene(self) -> None:
        rules = SceneRules()
        violations = rules.validate(_scene())
        assert len(violations) == 0

    def test_fails_missing_title_and_style(self) -> None:
        rules = SceneRules()
        violations = rules.validate(_scene(title=""))
        assert len(violations) >= 1
        rules_found = {v.rule for v in violations}
        assert "scene_needs_title_or_style" in rules_found
