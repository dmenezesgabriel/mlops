from pydantic import ValidationError
from videos.domain.value_objects.quality import QualityReport, RuleViolation


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
