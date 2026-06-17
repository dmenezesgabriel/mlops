from videos.application.use_cases.quality_gate import QualityGate
from videos.domain.value_objects.layout import LayoutSpec
from videos.domain.value_objects.quality import RuleViolation
from videos.domain.value_objects.scene_spec import SceneSpec


def _make_scene(scene_id: str = "s1") -> SceneSpec:
    return SceneSpec(
        scene_id=scene_id,
        title="Title",
        goal="Goal",
        duration_seconds=5.0,
        layout=LayoutSpec(regions=()),
    )


class _AlwaysFail:
    """ValidatorProtocol stub that always returns one violation."""

    def validate(self, scene: SceneSpec) -> list[RuleViolation]:
        return [
            RuleViolation(scene_id=scene.scene_id, rule="r", suggestion="fix")
        ]


class TestQualityGate:
    def test_passes_with_no_validators(self) -> None:
        gate = QualityGate(validators=[])
        report = gate.validate([_make_scene()])
        assert report.passed is True

    def test_returns_failed_report_when_validator_finds_violations(
        self,
    ) -> None:
        gate = QualityGate(validators=[_AlwaysFail()])
        report = gate.validate([_make_scene()])
        assert not report.passed
        assert len(report.violations) == 1
