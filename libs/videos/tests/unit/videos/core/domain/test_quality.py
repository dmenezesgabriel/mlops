import pytest
from videos.core.domain.quality import QualityReport, RuleViolation

VIOLATION = RuleViolation(
    scene_id="s1",
    object_id="o1",
    rule="max_words_per_text_block",
    actual=38,
    expected="<= 14",
    suggestion="Split this explanation",
)


class TestRuleViolation:
    def test_stores_fields(self) -> None:
        assert VIOLATION.scene_id == "s1"
        assert VIOLATION.object_id == "o1"
        assert VIOLATION.rule == "max_words_per_text_block"
        assert VIOLATION.actual == 38
        assert VIOLATION.suggestion == "Split this explanation"


class TestQualityReport:
    def test_passed_without_violations(self) -> None:
        report = QualityReport(passed=True)
        assert report.passed
        assert report.violations == ()

    def test_failed_with_violations(self) -> None:
        report = QualityReport(passed=False, violations=(VIOLATION,))
        assert not report.passed
        assert len(report.violations) == 1

    def test_rejects_passed_with_violations(self) -> None:
        with pytest.raises(ValueError, match="passed=True but has violations"):
            QualityReport(passed=True, violations=(VIOLATION,))

    def test_rejects_failed_without_violations(self) -> None:
        with pytest.raises(
            ValueError, match="passed=False but has no violations"
        ):
            QualityReport(passed=False)
