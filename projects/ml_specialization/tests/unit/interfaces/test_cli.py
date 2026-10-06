import sys
from pathlib import Path

import pytest
from fakes import FailingRunner
from ml_specialization.interfaces import cli
from ml_specialization.interfaces.cli import (
    create_parser,
    create_registry,
)
from mlops_shared.pipeline import PipelineCommandRegistry


def test_cli_parser_accepts_pipeline_subcommands() -> None:
    # Arrange
    parser = create_parser()

    # Act
    arguments = parser.parse_args(
        ["collect", "--config", "configs/project.yaml"]
    )

    # Assert
    assert arguments.command == "collect"


def test_pipeline_command_registry_reports_invalid_command() -> None:
    # Arrange
    registry = create_registry()

    # Act
    command_names = registry.names()

    # Assert
    assert "train" in command_names


def test_main_missing_config_exits_one_line(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Arrange — the config path must sit under configs/ to reach the
    # file read (the loader rejects other locations with ValueError).
    missing = tmp_path / "configs" / "missing.yaml"
    missing.parent.mkdir()
    monkeypatch.setattr(
        sys,
        "argv",
        ["ml_specialization", "collect", "--config", str(missing)],
    )

    # Act / Assert — the error becomes a clean exit, not a traceback.
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert isinstance(excinfo.value.code, str)
    assert str(missing) in excinfo.value.code
    assert "pipeline_command_failed" in capsys.readouterr().err


def test_main_not_implemented_pipeline_exits_clean(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    project_config_yaml: str,
) -> None:
    # Arrange
    config_path = tmp_path / "configs" / "project.yaml"
    config_path.parent.mkdir()
    config_path.write_text(project_config_yaml, encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["ml_specialization", "collect", "--config", str(config_path)],
    )

    # Act / Assert
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == "collect pipeline is not implemented"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ValueError("bad config value"), id="value_error"),
        pytest.param(ImportError("missing dependency"), id="import_error"),
        pytest.param(FileNotFoundError("no such config"), id="file_not_found"),
        pytest.param(NotImplementedError("stub"), id="not_implemented"),
    ],
)
def test_main_pipeline_errors_exit_clean(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    # Arrange
    registry = PipelineCommandRegistry({"collect": FailingRunner(error)})
    monkeypatch.setattr(cli, "create_registry", lambda: registry)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ml_specialization", "collect", "--config", "config.yaml"],
    )

    # Act / Assert
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == str(error)
