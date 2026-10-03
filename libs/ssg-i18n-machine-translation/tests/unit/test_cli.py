import sys
from pathlib import Path

import pytest
from ssg_i18n_machine_translation.domain.value_objects.translation_evaluation_report import (
    TranslationEvaluationReport,
)
from ssg_i18n_machine_translation.infrastructure.cli import (
    main,
    print_report_summary,
)


def test_main_prints_logs_on_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange — identical translation logs [FALLBACK] but stays under a
    # 100% threshold, so the run passes with a non-empty logs list.
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
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ssg-i18n-evaluate",
            "--source-dir",
            str(source_dir),
            "--translated-dir",
            str(translated_dir),
            "--max-fallback-rate-pct",
            "100",
        ],
    )

    # Act
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Assert — diagnostics stay visible even when the gate passes
    assert exc_info.value.code == 0
    assert "[FALLBACK]" in capsys.readouterr().out


def test_main_exits_clean_when_source_dir_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — a usage error must surface as SystemExit(msg) with a one-line
    # stderr, not a raw FileNotFoundError traceback.
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ssg-i18n-evaluate",
            "--source-dir",
            str(tmp_path / "missing"),
            "--translated-dir",
            str(translated_dir),
        ],
    )

    # Act
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Assert
    assert isinstance(exc_info.value.code, str)
    assert "source_dir" in exc_info.value.code


def test_main_exits_clean_on_invalid_locale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — Locale's BCP-47 ValueError must exit clean, not traceback.
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ssg-i18n-evaluate",
            "--source-dir",
            str(source_dir),
            "--translated-dir",
            str(translated_dir),
            "--locale",
            "bogus!",
        ],
    )

    # Act
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Assert
    assert isinstance(exc_info.value.code, str)
    assert "bogus!" in exc_info.value.code


def test_main_exits_clean_on_invalid_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — a list-root catalog yaml must exit naming the file, not crash
    # on 'list' object has no attribute 'get'.
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text("- a\n- b\n", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ssg-i18n-evaluate",
            "--source-dir",
            str(source_dir),
            "--translated-dir",
            str(translated_dir),
            "--catalog-path",
            str(catalog_path),
        ],
    )

    # Act
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Assert
    assert isinstance(exc_info.value.code, str)
    assert "catalog" in exc_info.value.code


def test_main_prints_failures_and_exits_one_on_failed_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange — a failing gate must exit rc=1 with the failure list printed.
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
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ssg-i18n-evaluate",
            "--source-dir",
            str(source_dir),
            "--translated-dir",
            str(translated_dir),
            "--max-fallback-rate-pct",
            "0",
        ],
    )

    # Act
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Assert
    assert exc_info.value.code == 1
    assert "FAILURES:" in capsys.readouterr().out


def test_main_prints_passed_and_exits_zero_on_clean_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange — no violations means no logs to print and a rc=0 PASSED.
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "doc1.md").write_text("Hello world.", encoding="utf-8")
    translated_dir = tmp_path / "translated"
    translated_dir.mkdir()
    (translated_dir / "doc1.md").write_text("Olá mundo.", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ssg-i18n-evaluate",
            "--source-dir",
            str(source_dir),
            "--translated-dir",
            str(translated_dir),
        ],
    )

    # Act
    with pytest.raises(SystemExit) as exc_info:
        main()

    # Assert
    assert exc_info.value.code == 0
    assert "PASSED" in capsys.readouterr().out


def test_print_report_summary_prints_bleu_when_present(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange — the BLEU line only prints when a catalog was evaluated.
    report = TranslationEvaluationReport(
        total_lines_evaluated=10,
        english_fallback_lines=0,
        english_fallback_rate_pct=0.0,
        wikilink_syntax_mismatches=0,
        table_formatting_mismatches=0,
        bleu_score_against_catalog=55.2,
        passed=True,
        failures=[],
        logs=[],
    )

    # Act
    print_report_summary(report)

    # Assert
    assert "BLEU score: 55.2" in capsys.readouterr().out
