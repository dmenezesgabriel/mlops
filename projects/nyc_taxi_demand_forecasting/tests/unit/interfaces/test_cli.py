import logging
import runpy
import sys
from functools import partial
from pathlib import Path

import pytest
from fakes import FailingRunner, FakeLoggingConfigurator, RecordingRunner
from mlops_shared.pipeline import PipelineCommandRegistry
from nyc_taxi_demand_forecasting.interfaces import cli
from nyc_taxi_demand_forecasting.interfaces.cli import (
    create_parser,
    create_registry,
    main,
    run_command,
)
from nyc_taxi_demand_forecasting.pipelines import collect

_CLI_LOGGER = "nyc_taxi_demand_forecasting.cli"


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


def test_run_command_logs_completed_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    runner = RecordingRunner()
    registry = PipelineCommandRegistry({"collect": runner})
    config_path = Path("configs/project.yaml")

    # Act
    with caplog.at_level(logging.INFO, logger=_CLI_LOGGER):
        run_command(registry, "collect", config_path)

    # Assert — a successful run logs started then completed.
    assert runner.calls == [config_path]
    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "pipeline_command_started",
        "pipeline_command_completed",
    ]


def test_run_command_propagates_runner_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange — a swallowed failure would still log "completed" and return.
    error = ValueError("bad config value")
    registry = PipelineCommandRegistry({"collect": FailingRunner(error)})
    config_path = Path("configs/project.yaml")

    # Act / Assert
    with (
        caplog.at_level(logging.INFO, logger=_CLI_LOGGER),
        pytest.raises(ValueError, match="bad config value"),
    ):
        run_command(registry, "collect", config_path)

    messages = [record.getMessage() for record in caplog.records]
    assert "pipeline_command_failed" in messages
    assert "pipeline_command_completed" not in messages


def test_run_command_rejects_unknown_command() -> None:
    # Arrange
    registry = PipelineCommandRegistry({})

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid pipeline command"):
        run_command(registry, "nope", Path("configs/project.yaml"))


def test_main_dispatches_parsed_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    runner = RecordingRunner()
    monkeypatch.setattr(
        cli,
        "create_registry",
        partial(PipelineCommandRegistry, {"collect": runner}),
    )
    monkeypatch.setattr(
        cli, "MlopsLoggingConfigurator", FakeLoggingConfigurator
    )
    monkeypatch.setattr(
        sys, "argv", ["cli", "collect", "--config", "conf.yaml"]
    )

    # Act
    main()

    # Assert
    assert runner.calls == [Path("conf.yaml")]
    assert FakeLoggingConfigurator.instances[0].configured


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
        [
            "nyc_taxi_demand_forecasting",
            "collect",
            "--config",
            str(missing),
        ],
    )

    # Act / Assert — the error becomes a clean exit, not a traceback.
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert isinstance(excinfo.value.code, str)
    assert str(missing) in excinfo.value.code
    assert "pipeline_command_failed" in capsys.readouterr().err


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ValueError("bad config value"), id="value_error"),
        pytest.param(ImportError("missing dependency"), id="import_error"),
        pytest.param(FileNotFoundError("no such config"), id="file_not_found"),
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
        [
            "nyc_taxi_demand_forecasting",
            "collect",
            "--config",
            "config.yaml",
        ],
    )

    # Act / Assert
    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == str(error)


def test_module_entrypoint_runs_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    runner = RecordingRunner()
    monkeypatch.setattr(collect, "run", runner)
    monkeypatch.setattr(
        "mlops_shared.logging.MlopsLoggingConfigurator",
        FakeLoggingConfigurator,
    )
    monkeypatch.setattr(
        sys, "argv", ["cli", "collect", "--config", "conf.yaml"]
    )

    # Act
    runpy.run_module(
        "nyc_taxi_demand_forecasting.interfaces.cli", run_name="__main__"
    )

    # Assert
    assert runner.calls == [Path("conf.yaml")]
