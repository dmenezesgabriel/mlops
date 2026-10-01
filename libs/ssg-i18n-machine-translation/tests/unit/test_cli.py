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
