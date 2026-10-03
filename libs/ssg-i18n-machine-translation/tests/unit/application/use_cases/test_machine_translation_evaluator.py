from pathlib import Path

import pytest
from ssg_i18n.domain.value_objects.locale import Locale
from ssg_i18n.infrastructure.in_memory_text_translator import (
    InMemoryTextTranslator,
)
from ssg_i18n_machine_translation.application.use_cases.machine_translation_evaluator import (
    MachineTranslationEvaluator,
)


def _doc_pair(
    tmp_path: Path, source_text: str, translated_text: str
) -> tuple[Path, Path]:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc.md").write_text(source_text, encoding="utf-8")
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc.md").write_text(translated_text, encoding="utf-8")
    return source_dir, translated_dir


class TestMachineTranslationEvaluator:
    def test_evaluate_empty_dirs_fails_with_no_source_files(
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
        assert report.passed is False
        assert any(
            "No '*.md' source files found" in failure
            for failure in report.failures
        )

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

    @pytest.mark.parametrize(
        "catalog_key",
        [
            "Start with a fairly long catalog sentence here",
            "The collector gathers quite a few long sentences",
        ],
        ids=["start-with-prefix", "the-collector-prefix"],
    )
    def test_bleu_includes_all_long_catalog_keys(
        self, tmp_path: Path, catalog_key: str
    ) -> None:
        # Prefix excludes baked project-corpus filters into generic
        # machinery — every long catalog key must reach the BLEU pass.
        source_dir, translated_dir = _doc_pair(
            tmp_path, "Short text.", "Texto curto."
        )
        catalog_path = tmp_path / "pt-BR.yaml"
        catalog_path.write_text(
            f'translations:\n  "{catalog_key}": "Tradução longa do catálogo"\n',
            encoding="utf-8",
        )

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator(
                {catalog_key: "Tradução longa do catálogo"}
            ),
            min_bleu_score=90.0,
        )
        report = evaluator.evaluate(
            source_dir,
            translated_dir,
            catalog_path=catalog_path,
            target_locale=Locale("pt-BR"),
        )

        assert report.bleu_score_against_catalog is not None
        assert report.bleu_score_against_catalog > 99.0
        assert report.passed is True

    @pytest.mark.parametrize(
        ("markdown", "expected_nodes"),
        [
            ("> A quoted english sentence", 1),
            ("> - item one\n> - item two", 2),
            ("Some Heading\n---", 1),
        ],
        ids=["quote", "quote-list", "setext-heading"],
    )
    def test_extracted_blocks_evaluated_for_fallback(
        self, tmp_path: Path, markdown: str, expected_nodes: int
    ) -> None:
        # The translator translates Quote/SetextHeading subtrees — the
        # evaluator must see the same nodes or their fallback is invisible.
        source_dir, translated_dir = _doc_pair(tmp_path, markdown, markdown)

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
            max_fallback_rate_pct=0.0,
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.total_lines_evaluated == expected_nodes
        assert report.english_fallback_lines == expected_nodes
        assert report.passed is False

    def test_translated_quote_is_evaluated(self, tmp_path: Path) -> None:
        source_dir, translated_dir = _doc_pair(
            tmp_path, "> A quoted sentence", "> Uma frase citada"
        )

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.total_lines_evaluated == 1
        assert report.english_fallback_lines == 0
        assert report.passed is True

    def test_jinja_paragraph_evaluated_for_fallback(
        self, tmp_path: Path
    ) -> None:
        # {{…}} spans are protected through the translator, so the
        # paragraph is translatable — dropping it hid whole-node fallback.
        markdown = 'Text with {{ include_source("a.py") }} inside'
        source_dir, translated_dir = _doc_pair(tmp_path, markdown, markdown)

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
            max_fallback_rate_pct=0.0,
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.english_fallback_lines == 1
        assert report.passed is False

    @pytest.mark.parametrize(
        ("source_text", "translated_text"),
        [
            (
                'Run {{ include_source("a.py") }} now',
                "Execute agora",
            ),
            (
                "See {{ a }} and {{ b }} here",
                "Veja {{ b }} e {{ a }} aqui",
            ),
            (
                "Text {% raw %} marker end",
                "Texto marcador final",
            ),
        ],
        ids=["dropped-directive", "reordered-directives", "dropped-tag"],
    )
    def test_directive_span_divergence_fails(
        self, tmp_path: Path, source_text: str, translated_text: str
    ) -> None:
        # Placeholder-integrity convention (Weblate/compare-locales/
        # msgfmt): protected spans must appear verbatim in the target.
        source_dir, translated_dir = _doc_pair(
            tmp_path, source_text, translated_text
        )

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.passed is False
        assert any(
            "[DIRECTIVE MISMATCH]" in failure for failure in report.failures
        )

    def test_verbatim_directive_passes(self, tmp_path: Path) -> None:
        source_dir, translated_dir = _doc_pair(
            tmp_path,
            'Run {{ include_source("a.py") }} now',
            'Execute {{ include_source("a.py") }} agora',
        )

        evaluator = MachineTranslationEvaluator(
            translator=InMemoryTextTranslator({}),
        )
        report = evaluator.evaluate(source_dir, translated_dir)

        assert report.passed is True
        assert report.total_lines_evaluated == 1
