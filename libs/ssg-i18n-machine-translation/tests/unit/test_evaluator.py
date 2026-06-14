from pathlib import Path

from ssg_i18n.application.translation import InMemoryTextTranslator
from ssg_i18n.domain.locale import Locale
from ssg_i18n_machine_translation.application.evaluator import (
    MachineTranslationEvaluator,
)


def test_evaluator_passes_when_all_metrics_within_thresholds(
    tmp_path: Path,
) -> None:
    # Arrange
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text(
        "Hello world. This is a sentence.", encoding="utf-8"
    )

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text(
        "Olá mundo. Esta é uma frase.", encoding="utf-8"
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
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text(
        "Hello world. This is a sentence.", encoding="utf-8"
    )

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text(
        "Hello world. This is a sentence.", encoding="utf-8"
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
    assert any(
        "Fallback rate 100.00% exceeds threshold 5.00%" in f
        for f in report.failures
    )
    assert any("[FALLBACK] In 'doc1.md'" in log for log in report.logs)


def test_evaluator_fails_on_wikilink_mismatch(tmp_path: Path) -> None:
    # Arrange
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text(
        "See [[link]] for details.", encoding="utf-8"
    )

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text(
        "Veja link para detalhes.", encoding="utf-8"
    )

    evaluator = MachineTranslationEvaluator(
        max_wikilink_syntax_mismatches=0,
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert not report.passed
    assert report.wikilink_syntax_mismatches == 1
    assert any(
        "Wikilink syntax mismatches 1 exceeds threshold 0" in f
        for f in report.failures
    )
    assert any(
        "[WIKILINK MISMATCH] In 'doc1.md'" in log for log in report.logs
    )


def test_evaluator_fails_on_table_mismatch(tmp_path: Path) -> None:
    # Arrange
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text(
        "| Col 1 | Col 2 |\n", encoding="utf-8"
    )

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text("| Col 1 |\n", encoding="utf-8")

    evaluator = MachineTranslationEvaluator(
        max_table_formatting_mismatches=0,
    )

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert not report.passed
    assert report.table_formatting_mismatches == 1
    assert any(
        "Table formatting mismatches 1 exceeds threshold 0" in f
        for f in report.failures
    )
    assert any("[TABLE MISMATCH] In 'doc1.md'" in log for log in report.logs)


def test_evaluator_calculates_bleu_score_and_enforces_threshold(
    tmp_path: Path,
) -> None:
    # Arrange
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text("Short text.", encoding="utf-8")

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text("Texto curto.", encoding="utf-8")

    catalog_path = tmp_path / "pt-BR.yaml"
    catalog_path.write_text(
        "translations:\n"
        "  This is a long sentence for testing: Esta é uma frase longa de teste\n",
        encoding="utf-8",
    )

    # We mock translator to return the exact translation for high BLEU
    mock_translator = InMemoryTextTranslator(
        {
            "This is a long sentence for testing": "Esta é uma frase longa de teste"
        }
    )
    evaluator_high = MachineTranslationEvaluator(
        translator=mock_translator,
        min_bleu_score=90.0,
    )

    # We mock translator to return bad translation for low BLEU
    bad_translator = InMemoryTextTranslator(
        {
            "This is a long sentence for testing": "Completamente diferente de tudo"
        }
    )
    evaluator_low = MachineTranslationEvaluator(
        translator=bad_translator,
        min_bleu_score=90.0,
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
    assert any(
        "BLEU score" in f and "is below threshold 90.00" in f
        for f in report_low.failures
    )


def test_evaluator_handles_node_count_mismatches_gracefully(
    tmp_path: Path,
) -> None:
    # Arrange
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text("Line 1.\n\nLine 2.", encoding="utf-8")

    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text("Line 1.", encoding="utf-8")

    evaluator = MachineTranslationEvaluator(max_fallback_rate_pct=100.0)

    # Act
    report = evaluator.evaluate(source_dir, translated_dir)

    # Assert
    assert report.passed  # Since zip length will just evaluate matched nodes, but structure mismatch log is generated
    assert any(
        "[STRUCTURE MISMATCH] File 'doc1.md' has 2 source nodes, but 'doc1.md' has 1 translated nodes."
        in log
        for log in report.logs
    )
