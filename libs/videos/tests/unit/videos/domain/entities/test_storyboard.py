import pytest
from videos.domain.entities.storyboard import Storyboard
from videos.domain.value_objects.layout import LayoutSpec
from videos.domain.value_objects.scene_spec import SceneSpec


def _make_scene(scene_id: str) -> SceneSpec:
    return SceneSpec(
        scene_id=scene_id,
        title="T",
        goal="G",
        duration_seconds=1.0,
        layout=LayoutSpec(regions=()),
    )


class TestStoryboard:
    def test_valid_storyboard_creation(self) -> None:
        sb = Storyboard(scenes=[_make_scene("s1")])
        assert len(sb.scenes) == 1

    def test_storyboard_rejects_empty_scenes(self) -> None:
        with pytest.raises(ValueError, match="at least one scene"):
            Storyboard(scenes=[])

    def test_storyboard_rejects_duplicate_scene_ids(self) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            Storyboard(scenes=[_make_scene("s1"), _make_scene("s1")])

    def test_total_expected_duration(self) -> None:
        sb = Storyboard(scenes=[_make_scene("s1"), _make_scene("s2")])
        assert sb.total_expected_duration == 2.0
