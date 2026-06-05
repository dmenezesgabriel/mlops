from videos.core.application.quality_gate import QualityGate
from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import SceneSpec, VisualObject


def _valid_scene() -> SceneSpec:
    return SceneSpec(
        scene_id="s1",
        title="Test",
        goal="A clear educational goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.BODY)),
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
        ),
    )


class TestQualityGate:
    def test_passes_valid_scene(self) -> None:
        gate = QualityGate()
        report = gate.validate([_valid_scene()])
        assert report.passed

    def test_fails_scene_with_unknown_region(self) -> None:
        gate = QualityGate()
        scene = SceneSpec(
            scene_id="s1",
            title="Test",
            goal="Goal",
            duration_seconds=5.0,
            layout=LayoutSpec(),
            visual_objects=(
                VisualObject(
                    object_id="o1",
                    region="invalid_region",
                    semantic_purpose="Display",
                ),
            ),
        )
        report = gate.validate([scene])
        assert not report.passed
        violations = {v.rule for v in report.violations}
        assert "unknown_layout_region" in violations

    def test_fails_scene_without_title_or_style(self) -> None:
        gate = QualityGate()
        scene = SceneSpec(
            scene_id="s1",
            title="",
            goal="Has a goal but no title",
            duration_seconds=5.0,
            layout=LayoutSpec(),
        )
        report = gate.validate([scene])
        assert not report.passed
        violations = {v.rule for v in report.violations}
        assert "scene_needs_title_or_style" in violations
