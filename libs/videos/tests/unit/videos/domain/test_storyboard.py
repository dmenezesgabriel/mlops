import pytest
from videos.domain.entities.storyboard import Storyboard
from videos.domain.value_objects.layout import LayoutRegion, LayoutSpec
from videos.domain.value_objects.scene_spec import SceneSpec


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

    def test_scenes_returns_tuple(self) -> None:
        scene = _scene("s1")
        sb = Storyboard(scenes=[scene])
        scenes = sb.scenes
        assert isinstance(scenes, tuple)
        assert scenes == (scene,)
