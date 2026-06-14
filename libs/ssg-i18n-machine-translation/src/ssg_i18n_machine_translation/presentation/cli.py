import argparse
import sys
from pathlib import Path

from ssg_i18n.domain.locale import Locale

from ssg_i18n_machine_translation.evaluator import (
    MachineTranslationEvaluator,
    TranslationEvaluationReport,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate machine translation metrics."
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--translated-dir", required=True, type=Path)
    parser.add_argument("--catalog-path", type=Path)
    parser.add_argument("--locale", default="pt-BR")
    parser.add_argument("--max-fallback-rate-pct", type=float, default=8.0)
    parser.add_argument(
        "--max-wikilink-syntax-mismatches", type=int, default=0
    )
    parser.add_argument(
        "--max-table-formatting-mismatches", type=int, default=0
    )
    parser.add_argument("--min-bleu-score", type=float, default=40.0)
    return parser.parse_args()


def print_report_summary(report: TranslationEvaluationReport) -> None:
    print("=== Translation Evaluation Report ===")
    print(f"Total lines evaluated: {report.total_lines_evaluated}")
    print(
        f"Fallback lines: {report.english_fallback_lines} ({report.english_fallback_rate_pct}%)"
    )
    print(f"Wikilink syntax mismatches: {report.wikilink_syntax_mismatches}")
    print(f"Table formatting mismatches: {report.table_formatting_mismatches}")
    if report.bleu_score_against_catalog is not None:
        print(f"BLEU score: {report.bleu_score_against_catalog}")


def print_failures_and_logs(report: TranslationEvaluationReport) -> None:
    print("\nFAILURES:")
    for failure in report.failures:
        print(f"- {failure}")
    print("\nLOGS / JUSTIFICATIONS:")
    for log in report.logs:
        print(log)


def main() -> None:
    args = parse_arguments()
    evaluator = MachineTranslationEvaluator(
        max_fallback_rate_pct=args.max_fallback_rate_pct,
        max_wikilink_syntax_mismatches=args.max_wikilink_syntax_mismatches,
        max_table_formatting_mismatches=args.max_table_formatting_mismatches,
        min_bleu_score=args.min_bleu_score,
    )
    report = evaluator.evaluate(
        source_dir=args.source_dir,
        translated_dir=args.translated_dir,
        catalog_path=args.catalog_path,
        target_locale=Locale(args.locale),
    )
    print_report_summary(report)
    if not report.passed:
        print_failures_and_logs(report)
        sys.exit(1)
    print("\nEvaluation PASSED!")
    sys.exit(0)
