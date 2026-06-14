from pathlib import Path

from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    MachineTranslationEvaluator,
)


class TestMachineTranslationEvaluator:
    def test_evaluate_empty_dirs_returns_zero_total(
        self, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "source"
        translated_dir = tmp_path / "translated"
        source_dir.mkdir()
        translated_dir.mkdir()

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({})
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.total_lines_evaluated == 0
        assert report.passed is True

    def test_evaluate_identical_files_reports_fallback(
        self, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "source"
        translated_dir = tmp_path / "translated"
        source_dir.mkdir()
        translated_dir.mkdir()
        (source_dir / "doc.md").write_text(
            "This is a long English sentence here.", encoding="utf-8"
        )
        (translated_dir / "doc.md").write_text(
            "This is a long English sentence here.", encoding="utf-8"
        )

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
            max_fallback_rate_pct=0.0,
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.english_fallback_lines > 0
        assert report.passed is False

    def test_evaluate_translated_files_passes_below_threshold(
        self, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "source"
        translated_dir = tmp_path / "translated"
        source_dir.mkdir()
        translated_dir.mkdir()
        (source_dir / "doc.md").write_text("Hello world.", encoding="utf-8")
        (translated_dir / "doc.md").write_text("Olá mundo.", encoding="utf-8")

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.english_fallback_lines == 0
        assert report.passed is True
