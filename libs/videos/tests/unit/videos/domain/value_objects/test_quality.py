import pytest
from pydantic import ValidationError
from videos.domain.value_objects.quality import QualityReport, RuleViolation


class TestRuleViolation:
    def test_rejects_non_scalar_actual(self) -> None:
        with pytest.raises(ValidationError):
            RuleViolation(
                scene_id="s1", rule="r", suggestion="fix", actual=object()
            )

    def test_rejects_collection_actual(self) -> None:
        with pytest.raises(ValidationError):
            RuleViolation(
                scene_id="s1", rule="r", suggestion="fix", actual={"a", "b"}
            )

    @pytest.mark.parametrize("value", ["text", 38, 1.5, None])
    def test_accepts_scalar_actual(self, value: object) -> None:
        v = RuleViolation(
            scene_id="s1", rule="r", suggestion="fix", actual=value
        )
        assert v.actual == value


class TestQualityReport:
    def test_passed_with_no_violations(self) -> None:
        report = QualityReport(passed=True)
        assert report.passed is True

    def test_failed_requires_violations(self) -> None:
        import pytest

        with pytest.raises(ValidationError):
            QualityReport(passed=False)

    def test_passed_rejects_violations(self) -> None:
        import pytest

        with pytest.raises(ValidationError):
            QualityReport(
                passed=True,
                violations=(
                    RuleViolation(
                        scene_id="s1", rule="r", suggestion="fix it"
                    ),
                ),
            )
