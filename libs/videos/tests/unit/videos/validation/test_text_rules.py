from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import SceneSpec, VisualObject
from videos.validation.text_rules import TextRules


def _scene(visual_objects: tuple[VisualObject, ...] = ()) -> SceneSpec:
    return SceneSpec(
        scene_id="test_scene",
        title="Test",
        goal="Test goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        visual_objects=visual_objects,
    )


class TestTextRules:
    def test_passes_short_text(self) -> None:
        rules = TextRules()
        scene = _scene(
            visual_objects=(
                VisualObject(object_id="title_1", region="title", semantic_purpose="Hello world"),
            )
        )
        violations = rules.validate(scene)
        assert len(violations) == 0

    def test_fails_excessive_words(self) -> None:
        rules = TextRules()
        long_text = "word " * 20
        scene = _scene(
            visual_objects=(
                VisualObject(object_id="body_1", region="body", semantic_purpose=long_text),
            )
        )
        violations = rules.validate(scene)
        assert len(violations) >= 1
        assert violations[0].rule == "max_words_per_text_block"

    def test_passes_empty_visual_objects(self) -> None:
        rules = TextRules()
        scene = _scene()
        violations = rules.validate(scene)
        assert len(violations) == 0
