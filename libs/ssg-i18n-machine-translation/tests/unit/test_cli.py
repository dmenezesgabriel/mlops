import sys
from pathlib import Path

import pytest
from ssg_i18n_machine_translation.infrastructure.cli import main


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
