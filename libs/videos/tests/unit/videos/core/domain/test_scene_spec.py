import pytest
from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import SceneSpec, VisualObject


class TestSceneSpec:
    def test_rejects_empty_scene_id(self) -> None:
        with pytest.raises(ValueError, match="scene_id"):
            SceneSpec(
                scene_id="",
                title="T",
                goal="G",
                duration_seconds=5.0,
                layout=LayoutSpec(),
            )

    def test_rejects_empty_goal(self) -> None:
        with pytest.raises(ValueError, match="goal"):
            SceneSpec(
                scene_id="s1",
                title="T",
                goal="",
                duration_seconds=5.0,
                layout=LayoutSpec(),
            )

    def test_rejects_zero_duration(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds"):
            SceneSpec(
                scene_id="s1",
                title="T",
                goal="G",
                duration_seconds=0,
                layout=LayoutSpec(),
            )

    def test_rejects_negative_duration(self) -> None:
        with pytest.raises(ValueError, match="duration_seconds"):
            SceneSpec(
                scene_id="s1",
                title="T",
                goal="G",
                duration_seconds=-1.0,
                layout=LayoutSpec(),
            )

    def test_accepts_valid_spec(self) -> None:
        spec = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Test goal",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
            visual_objects=(
                VisualObject(
                    object_id="title_1",
                    region="title",
                    semantic_purpose="Display title",
                ),
            ),
        )
        assert spec.scene_id == "s1"
        assert spec.duration_seconds == 5.0
        assert len(spec.visual_objects) == 1


class TestVisualObject:
    def test_stores_fields(self) -> None:
        vo = VisualObject(
            object_id="o1", region="title", semantic_purpose="Display"
        )
        assert vo.object_id == "o1"
        assert vo.region == "title"
        assert vo.semantic_purpose == "Display"
