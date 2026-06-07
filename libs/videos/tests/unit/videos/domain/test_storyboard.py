import pytest
from videos.domain.layout import LayoutRegion, LayoutSpec
from videos.domain.scene_spec import SceneSpec
from videos.domain.storyboard import Storyboard


def _scene(scene_id: str) -> SceneSpec:
    return SceneSpec(
        scene_id=scene_id,
        title="Test",
        goal="Test goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
    )


class TestStoryboard:
    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="at least one scene"):
            Storyboard(scenes=[])

    def test_accepts_single_scene(self) -> None:
        sb = Storyboard(scenes=[_scene("s1")])
        assert len(sb.scenes) == 1

    def test_rejects_duplicate_scene_id(self) -> None:
        with pytest.raises(ValueError, match="Duplicate scene_id"):
            Storyboard(scenes=[_scene("dup"), _scene("dup")])

    def test_total_expected_duration_sums_scenes(self) -> None:
        s1 = _scene("s1")
        s2 = SceneSpec(
            scene_id="s2",
            title="Test2",
            goal="Goal2",
            duration_seconds=3.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        sb = Storyboard(scenes=[s1, s2])
        assert sb.total_expected_duration == 8.0

    def test_scenes_returns_tuple(self) -> None:
        sb = Storyboard(scenes=[_scene("s1")])
        scenes = sb.scenes
        assert isinstance(scenes, tuple)
        assert scenes == tuple(sb._scenes)
