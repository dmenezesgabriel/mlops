from videos.domain.layout import LayoutSpec
from videos.domain.scene_spec import ComponentSpec, SceneSpec, VisualObject
from videos.domain.validation.layout_rules import LayoutRules


def _scene(
    visual_objects: tuple[VisualObject, ...] = (),
    components: tuple[ComponentSpec, ...] = (),
) -> SceneSpec:
    return SceneSpec(
        scene_id="test_scene",
        title="Test",
        goal="Test goal",
        duration_seconds=5.0,
        layout=LayoutSpec(),
        visual_objects=visual_objects,
        components=components,
    )


class TestLayoutRules:
    def test_passes_valid_regions(self) -> None:
        rules = LayoutRules()
        scene = _scene(
            visual_objects=(
                VisualObject(
                    object_id="title_1",
                    region="title",
                    semantic_purpose="Display",
                ),
                VisualObject(
                    object_id="body_1",
                    region="body",
                    semantic_purpose="Explain",
                ),
            )
        )
        violations = rules.validate(scene)
        assert len(violations) == 0

    def test_fails_unknown_region(self) -> None:
        rules = LayoutRules()
        scene = _scene(
            visual_objects=(
                VisualObject(
                    object_id="bad",
                    region="invalid_region",
                    semantic_purpose="Display",
                ),
            )
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "unknown_layout_region"

    def test_fails_empty_region(self) -> None:
        rules = LayoutRules()
        scene = _scene(
            visual_objects=(
                VisualObject(
                    object_id="bad", region="", semantic_purpose="Display"
                ),
            )
        )
        violations = rules.validate(scene)
        assert len(violations) >= 1

    def test_fails_diagram_without_labels(self) -> None:
        rules = LayoutRules()
        comp = ComponentSpec(
            type="diagram",
            region="diagram",
            props={"kind": "cycle"},
        )
        scene = _scene(components=(comp,))
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "diagram_requires_labels"
        assert "labels" in violations[0].suggestion
