from pathlib import Path

import pytest
from ssg_i18n.application.translation import InMemoryTextTranslator
from ssg_i18n.domain.locale import Locale
from ssg_i18n_machine_translation.application.evaluator import (
    MachineTranslationEvaluator,
)
from ssg_i18n_machine_translation.domain.value_objects.translation_evaluation_report import (
    TranslationEvaluationReport,
)


def _doc_pair(
    tmp_path: Path, source_text: str, translated_text: str
) -> tuple[Path, Path]:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text(source_text, encoding="utf-8")

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text(translated_text, encoding="utf-8")
    return source_dir, translated_dir


def _failures_contain(
    report: TranslationEvaluationReport, fragment: str
) -> bool:
    return any(fragment in failure for failure in report.failures)


def _logs_contain(report: TranslationEvaluationReport, fragment: str) -> bool:
    return any(fragment in log for log in report.logs)


def test_evaluator_passes_when_all_metrics_within_thresholds(
    tmp_path: Path,
) -> None:
    # Arrange
    source_dir, translated_dir = _doc_pair(
        tmp_path,
        "Hello world. This is a sentence.",
        "Olá mundo. Esta é uma frase.",
    )
    evaluator = MachineTranslationEvaluator(
        max_fallback_rate_pct=10.0,
        max_wikilink_syntax_mismatches=0,
        max_table_formatting_mismatches=0,
        min_bleu_score=20.0,
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert report.passed
    assert report.total_lines_evaluated == 1
    assert report.english_fallback_lines == 0
    assert report.english_fallback_rate_pct == 0.0
    assert report.wikilink_syntax_mismatches == 0
    assert report.table_formatting_mismatches == 0
    assert len(report.failures) == 0


def test_evaluator_fails_on_fallback_rate_threshold(tmp_path: Path) -> None:
    # Arrange
    source_dir, translated_dir = _doc_pair(
        tmp_path,
        "Hello world. This is a sentence.",
        "Hello world. This is a sentence.",
    )
    # fallback rate is 100% (only len > 3 is checked, "Hello world" is 11 chars)
    evaluator = MachineTranslationEvaluator(
        max_fallback_rate_pct=5.0,
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert not report.passed
    assert report.english_fallback_lines == 1
    assert report.english_fallback_rate_pct == 100.0
    assert _failures_contain(
        report, "Fallback rate 100.00% exceeds threshold 5.00%"
    )
    assert _logs_contain(report, "[FALLBACK] In 'doc1.md'")


def test_evaluator_fails_on_wikilink_mismatch(tmp_path: Path) -> None:
    # Arrange
    source_dir, translated_dir = _doc_pair(
        tmp_path,
        "See [[link]] for details.",
        "Veja link para detalhes.",
    )
    evaluator = MachineTranslationEvaluator(
        max_wikilink_syntax_mismatches=0,
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert not report.passed
    assert report.wikilink_syntax_mismatches == 1
    assert _failures_contain(
        report, "Wikilink syntax mismatches 1 exceeds threshold 0"
    )
    assert _logs_contain(report, "[WIKILINK MISMATCH] In 'doc1.md'")


def test_evaluator_fails_on_table_mismatch(tmp_path: Path) -> None:
    # Arrange
    source_dir, translated_dir = _doc_pair(
        tmp_path,
        "| Col 1 | Col 2 |\n",
        "| Col 1 |\n",
    )
    evaluator = MachineTranslationEvaluator(
        max_table_formatting_mismatches=0,
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert not report.passed
    assert report.table_formatting_mismatches == 1
    assert _failures_contain(
        report, "Table formatting mismatches 1 exceeds threshold 0"
    )
    assert _logs_contain(report, "[TABLE MISMATCH] In 'doc1.md'")


def _catalog_evaluator(
    translated_sentence: str, min_bleu_score: float
) -> MachineTranslationEvaluator:
    # InMemoryTextTranslator returns the mapped translation verbatim, so the
    # BLEU score against the catalog is deterministic per mapping.
    translator = InMemoryTextTranslator(
        {"This is a long sentence for testing": translated_sentence}
    )
    return MachineTranslationEvaluator(
        translator=translator, min_bleu_score=min_bleu_score
    )


def test_evaluator_calculates_bleu_score_and_enforces_threshold(
    tmp_path: Path,
) -> None:
    # Arrange
    source_dir, translated_dir = _doc_pair(
        tmp_path, "Short text.", "Texto curto."
    )
    catalog_path = tmp_path / "pt-BR.yaml"
    catalog_path.write_text(
        "translations:\n"
        "  This is a long sentence for testing: Esta é uma frase longa de teste\n",
        encoding="utf-8",
    )

    # Exact-catalog translation scores high BLEU; a divergent one scores low.
    evaluator_high = _catalog_evaluator(
        "Esta é uma frase longa de teste", min_bleu_score=90.0
    )
    evaluator_low = _catalog_evaluator(
        "Completamente diferente de tudo", min_bleu_score=90.0
    )

    # Act
    report_high = evaluator_high.evaluate(
        source_dir,
        translated_dir,
        catalog_path=catalog_path,
        target_locale=Locale("pt-BR"),
    )
    report_low = evaluator_low.evaluate(
        source_dir,
        translated_dir,
        catalog_path=catalog_path,
        target_locale=Locale("pt-BR"),
    )

    # Assert
    assert report_high.passed
    assert report_high.bleu_score_against_catalog is not None
    assert report_high.bleu_score_against_catalog > 99.0

    assert not report_low.passed
    assert report_low.bleu_score_against_catalog is not None
    assert report_low.bleu_score_against_catalog < 10.0
    assert _failures_contain(report_low, "BLEU score")
    assert _failures_contain(report_low, "is below threshold 90.00")


def test_evaluator_fails_when_source_dir_missing(tmp_path: Path) -> None:
    # Arrange
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    evaluator = MachineTranslationEvaluator(
        translator=InMemoryTextTranslator({})
    )

    # Act / Assert — a gate must not pass on input it cannot read
    with pytest.raises(FileNotFoundError, match="source_dir"):
        evaluator.evaluate(tmp_path / "missing", translated_dir)


def test_evaluator_fails_when_translated_dir_missing(tmp_path: Path) -> None:
    # Arrange
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text("Hello world.", encoding="utf-8")
    evaluator = MachineTranslationEvaluator(
        translator=InMemoryTextTranslator({})
    )

    # Act / Assert
    with pytest.raises(FileNotFoundError, match="translated_dir"):
        evaluator.evaluate(source_dir, tmp_path / "missing")


def test_evaluator_fails_on_missing_translated_file(tmp_path: Path) -> None:
    # Arrange — two source files, only one translated
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text("Hello world.", encoding="utf-8")
    (source_dir / "doc2.md").write_text("Second page.", encoding="utf-8")
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text("Olá mundo.", encoding="utf-8")
    evaluator = MachineTranslationEvaluator(
        translator=InMemoryTextTranslator({})
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert — the present pair is still evaluated, but the gate fails
    assert not report.passed
    assert report.total_lines_evaluated == 1
    assert _failures_contain(report, "Missing translated file: 'doc2.md'")


def test_evaluator_fails_on_node_count_mismatch(
    tmp_path: Path,
) -> None:
    # Arrange
    source_dir, translated_dir = _doc_pair(
        tmp_path, "Line 1.\n\nLine 2.", "Line 1."
    )
    evaluator = MachineTranslationEvaluator(max_fallback_rate_pct=100.0)

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert — divergent structure is a failure; matched pairs still evaluate
    assert not report.passed
    assert report.total_lines_evaluated == 1
    assert _failures_contain(
        report,
        "[STRUCTURE MISMATCH] File 'doc1.md' has 2 source nodes, but 'doc1.md' has 1 translated nodes.",
    )
