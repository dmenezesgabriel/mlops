import sys
from pathlib import Path

import pytest
from mlops_shared.pipeline import PipelineCommandRegistry

from {{ cookiecutter.project_slug }}.interfaces import cli
from {{ cookiecutter.project_slug }}.interfaces.cli import (
    create_parser,
    create_registry,
)


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


class FailingRunner:
    """Pipeline runner stand-in raising a scripted exception."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def __call__(self, config_path: Path) -> None:
        raise self._error


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ValueError("bad config value"), id="value_error"),
        pytest.param(TypeError("bad config type"), id="type_error"),
        pytest.param(ImportError("missing dependency"), id="import_error"),
        pytest.param(FileNotFoundError("no such config"), id="file_not_found"),
        pytest.param(RuntimeError("wiring drift"), id="runtime_error"),
        pytest.param(NotImplementedError("stub"), id="not_implemented"),
    ],
)
def test_main_pipeline_errors_exit_clean(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    # Arrange — config/wiring errors must exit named, not as tracebacks.
    # RuntimeError also covers the stubs' NotImplementedError.
    registry = PipelineCommandRegistry({"collect": FailingRunner(error)})
    monkeypatch.setattr(cli, "create_registry", lambda: registry)
    monkeypatch.setattr(
        sys,
        "argv",
        ["dummy", "collect", "--config", "configs/project.yaml"],
    )

    # Act / Assert
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == str(error)


def test_main_missing_config_exits_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Arrange — the path must sit under configs/ to reach the file read.
    missing = tmp_path / "configs" / "missing.yaml"
    missing.parent.mkdir()
    monkeypatch.setattr(
        sys, "argv", ["dummy", "collect", "--config", str(missing)]
    )

    # Act / Assert — the error becomes a clean exit, not a traceback.
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert isinstance(excinfo.value.code, str)
    assert str(missing) in excinfo.value.code
