import logging
import runpy
import sys
from functools import partial
from pathlib import Path

import pytest
from fakes import FakeLoggingConfigurator
from mlops_shared.pipeline import PipelineCommandRegistry
from nyc_taxi_demand_forecasting.interfaces import cli
from nyc_taxi_demand_forecasting.interfaces.cli import (
    create_parser,
    create_registry,
    main,
    run_command,
)
from nyc_taxi_demand_forecasting.pipelines import collect


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


def test_run_command_invokes_registered_runner() -> None:
    # Arrange
    called_with: list[Path] = []

    def _probe(config_path: Path) -> None:
        called_with.append(config_path)

    registry = PipelineCommandRegistry({"probe": _probe})

    # Act
    run_command(registry, "probe", Path("configs/project.yaml"))

    # Assert
    assert called_with == [Path("configs/project.yaml")]


def test_run_command_reraises_runner_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Arrange
    def _failing(config_path: Path) -> None:
        raise RuntimeError("boom")

    registry = PipelineCommandRegistry({"probe": _failing})

    # Act / Assert
    with caplog.at_level(
        logging.ERROR, logger="nyc_taxi_demand_forecasting.cli"
    ):
        with pytest.raises(RuntimeError, match="boom"):
            run_command(registry, "probe", Path("configs/project.yaml"))
    assert "pipeline_command_failed" in caplog.text


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
    called_with: list[Path] = []

    def _probe(config_path: Path) -> None:
        called_with.append(config_path)

    monkeypatch.setattr(
        cli,
        "create_registry",
        partial(PipelineCommandRegistry, {"collect": _probe}),
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
    assert called_with == [Path("conf.yaml")]
    assert FakeLoggingConfigurator.instances[0].configured


def test_module_entrypoint_runs_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    called_with: list[Path] = []

    def _collect(config_path: Path) -> None:
        called_with.append(config_path)

    monkeypatch.setattr(collect, "run", _collect)
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
    assert called_with == [Path("conf.yaml")]
