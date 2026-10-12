"""Step definitions for the pipeline-CLI dispatch BDD feature.

Steps drive `cli.main()` with real argv — the assembled
argv→registry→stub-run→named-exit loop the unit pins reach only
piecemeal. Every pipeline is a designed stub (it loads the config, then
raises its named NotImplementedError), so the user-visible contract
pinned here is the named-error exit shape, not a successful run.
"""

import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from ml_specialization.interfaces import cli
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/pipelines_cli.feature")


@dataclass
class CliRun:
    """State shared between the given/when/then steps of a scenario."""

    config_path: Path
    exit_code: int | str | None = 0
    stderr: str = ""


@pytest.fixture(autouse=True)
def _restore_root_handlers() -> Iterator[None]:
    """`cli.main()` reconfigures root logging with `force=True` per call."""
    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_level = root_logger.level
    yield
    root_logger.handlers[:] = previous_handlers
    root_logger.level = previous_level


@pytest.fixture
def run(tmp_path: Path) -> CliRun:
    return CliRun(config_path=tmp_path / "configs" / "project.yaml")


@given("a valid project config exists")
def _valid_config(run: CliRun, project_config_yaml: str) -> None:
    # Arrange
    run.config_path.parent.mkdir(parents=True)
    run.config_path.write_text(project_config_yaml, encoding="utf-8")


@given("no project config exists")
def _missing_config(run: CliRun) -> None:
    # Arrange — the parent is named configs/ so the loader's location
    # guard passes and the failure is the absent file itself.
    run.config_path.parent.mkdir(parents=True)


@when(parsers.parse('I run the pipeline command "{command}"'))
def _run_command(
    run: CliRun,
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Act
    monkeypatch.setattr(
        sys,
        "argv",
        ["ml_specialization", command, "--config", str(run.config_path)],
    )
    try:
        cli.main()
    except SystemExit as exc:
        run.exit_code = exc.code
    run.stderr = capsys.readouterr().err


@then(parsers.parse('the command exits reporting "{message}"'))
def _exit_message(run: CliRun, message: str) -> None:
    # Assert — SystemExit carries the one-line message a real invocation
    # would print at exit.
    assert run.exit_code == message


@then("the command exits reporting the missing config path")
def _exit_missing_path(run: CliRun) -> None:
    # Assert
    assert isinstance(run.exit_code, str)
    assert str(run.config_path) in run.exit_code


@then(parsers.parse("the command exits with code {code:d}"))
def _exit_code(run: CliRun, code: int) -> None:
    # Assert
    assert run.exit_code == code


@then(parsers.parse('the failure log names "{command}"'))
def _failure_log_names(run: CliRun, command: str) -> None:
    # Assert — the JSON log record carries the command context field.
    assert f'"command": "{command}"' in run.stderr


@then(parsers.parse('stderr shows "{needle}"'))
def _stderr_shows(run: CliRun, needle: str) -> None:
    # Assert
    assert needle in run.stderr


@then(parsers.parse('stderr does not show "{needle}"'))
def _stderr_lacks(run: CliRun, needle: str) -> None:
    # Assert — a failed dispatch must never log the completed event.
    assert needle not in run.stderr
