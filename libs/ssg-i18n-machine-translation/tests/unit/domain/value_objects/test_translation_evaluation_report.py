from ssg_i18n_machine_translation.domain.value_objects.translation_evaluation_report import (
    TranslationEvaluationReport,
)


class TestTranslationEvaluationReport:
    def test_passed_true_when_no_failures(self) -> None:
        report = TranslationEvaluationReport(
            total_lines_evaluated=10,
            english_fallback_lines=0,
            english_fallback_rate_pct=0.0,
            wikilink_syntax_mismatches=0,
            table_formatting_mismatches=0,
            bleu_score_against_catalog=None,
            passed=True,
            failures=[],
            logs=[],
        )
        assert report.passed is True
        assert report.failures == []

    def test_passed_false_when_failures_present(self) -> None:
        report = TranslationEvaluationReport(
            total_lines_evaluated=10,
            english_fallback_lines=5,
            english_fallback_rate_pct=50.0,
            wikilink_syntax_mismatches=0,
            table_formatting_mismatches=0,
            bleu_score_against_catalog=None,
            passed=False,
            failures=["Fallback rate too high"],
            logs=[],
        )
        assert report.passed is False
        assert len(report.failures) == 1
