import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from cookiecutter.exceptions import (
    FailedHookException,
    OutputDirExistsException,
)
from data_science_scaffold.scaffold import PROJECTS_DIR, main


def test_main_usage_names_module_entry_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    monkeypatch.setattr(sys, "argv", ["scaffold"])

    # Act & Assert — the usage string must name the real entry point.
    with pytest.raises(SystemExit, match="data_science_scaffold.scaffold"):
        main()


class _RecordingGenerate:
    """Named fake capturing the arguments main() wires into generate()."""

    def __init__(self, rendered: Path) -> None:
        self.calls: list[tuple[str, Path]] = []
        self._rendered = rendered

    def __call__(self, slug: str, output_dir: str | Path) -> Path:
        self.calls.append((slug, Path(output_dir)))
        return self._rendered


def test_main_renders_slug_into_repo_projects_dir(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    # Arrange — the stub owns rendering so the code under test is
    # main()'s argument wiring and result print.
    fake = _RecordingGenerate(tmp_path / "dummy_test_proj")
    monkeypatch.setattr(sys, "argv", ["scaffold", "dummy_test_proj"])
    monkeypatch.setattr("data_science_scaffold.scaffold.generate", fake)

    # Act
    main()

    # Assert
    assert fake.calls == [("dummy_test_proj", PROJECTS_DIR)]
    assert capsys.readouterr().out.strip() == (
        f"Rendered {tmp_path / 'dummy_test_proj'}"
    )


def _hook_failing_generate(slug: str, output_dir: str | Path) -> Path:
    raise FailedHookException("pre_gen hook failed")


def _collision_generate(slug: str, output_dir: str | Path) -> Path:
    raise OutputDirExistsException("project dir already exists")


@pytest.mark.parametrize(
    "generate_stub", [_hook_failing_generate, _collision_generate]
)
def test_main_reports_render_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    generate_stub: Callable[[str, str | Path], Path],
) -> None:
    # Arrange — cookiecutter failures are operator-facing (invalid slug,
    # existing project dir) and must not dump a traceback.
    monkeypatch.setattr(sys, "argv", ["scaffold", "dummy_test_proj"])
    monkeypatch.setattr(
        "data_science_scaffold.scaffold.generate", generate_stub
    )

    # Act & Assert — a clean SystemExit carries the failure; an uncaught
    # exception would surface as a traceback to the operator.
    with pytest.raises(SystemExit):
        main()
