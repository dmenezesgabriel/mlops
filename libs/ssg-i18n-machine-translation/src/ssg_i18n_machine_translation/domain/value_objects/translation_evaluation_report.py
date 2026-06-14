from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationEvaluationReport:
    """Aggregated evaluation results for a machine translation run.

    Example:
        TranslationEvaluationReport(
            total_lines_evaluated=100,
            english_fallback_lines=3,
            english_fallback_rate_pct=3.0,
            wikilink_syntax_mismatches=0,
            table_formatting_mismatches=0,
            bleu_score_against_catalog=55.2,
            passed=True,
            failures=[],
            logs=[],
        )
    """

    total_lines_evaluated: int
    english_fallback_lines: int
    english_fallback_rate_pct: float
    wikilink_syntax_mismatches: int
    table_formatting_mismatches: int
    bleu_score_against_catalog: float | None
    passed: bool
    failures: list[str]
    logs: list[str]
