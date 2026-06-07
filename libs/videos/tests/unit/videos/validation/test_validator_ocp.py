from __future__ import annotations

from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.quality import RuleViolation
from videos.core.domain.scene_spec import SceneSpec, VisualObject
from videos.validation.layout_rules import LayoutRules
from videos.validation.scene_rules import SceneRules
from videos.validation.text_rules import TextRules
from videos.validation.timeline_rules import (
    TimelineRules,
)


class TestLayoutRulesOCP:
    def test_default_rules_run(self) -> None:
        rules = LayoutRules()
        scene = SceneSpec(
            scene_id="s1",
            title="T",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
            visual_objects=(
                VisualObject(
                    object_id="o1", region="title", semantic_purpose="Test"
                ),
            ),
        )
        assert len(rules.validate(scene)) == 0

    def test_accepts_custom_rules(self) -> None:
        def always_fail(scene: SceneSpec) -> list[RuleViolation]:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="custom_rule",
                    suggestion="Always fails",
                )
            ]

        rules = LayoutRules(rules=[always_fail])
        scene = SceneSpec(
            scene_id="s1",
            title="T",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "custom_rule"


class TestTextRulesOCP:
    def test_accepts_custom_rules(self) -> None:
        def always_fail(scene: SceneSpec) -> list[RuleViolation]:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="custom_text",
                    suggestion="Always fails",
                )
            ]

        rules = TextRules(rules=[always_fail])
        scene = SceneSpec(
            scene_id="s1",
            title="T",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "custom_text"


class TestSceneRulesOCP:
    def test_accepts_custom_rules(self) -> None:
        def always_fail(scene: SceneSpec) -> list[RuleViolation]:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="custom_scene",
                    suggestion="Always fails",
                )
            ]

        rules = SceneRules(rules=[always_fail])
        scene = SceneSpec(
            scene_id="s1",
            title="",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "custom_scene"


class TestTimelineRulesOCP:
    def test_accepts_custom_rules(self) -> None:
        def always_fail(scene: SceneSpec) -> list[RuleViolation]:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="custom_timeline",
                    suggestion="Always fails",
                )
            ]

        rules = TimelineRules(rules=[always_fail])
        scene = SceneSpec(
            scene_id="s1",
            title="T",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        violations = rules.validate(scene)
        assert len(violations) == 1
        assert violations[0].rule == "custom_timeline"


class TestQualityGateOCP:
    def test_accepts_custom_rules(self) -> None:
        from videos.core.application.quality_gate import QualityGate
        from videos.core.domain.quality import RuleViolation

        def custom_validator(scene: SceneSpec) -> list[RuleViolation]:
            return [
                RuleViolation(
                    scene_id=scene.scene_id,
                    rule="custom_gate",
                    suggestion="Always fails",
                )
            ]

        gate = QualityGate(static_rules=[custom_validator])
        scene = SceneSpec(
            scene_id="s1",
            title="T",
            goal="G",
            duration_seconds=5.0,
            layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
        )
        report = gate.validate([scene])
        assert not report.passed
        violations = {v.rule for v in report.violations}
        assert "custom_gate" in violations
