"""Step definitions for the pipeline-CLI dispatch BDD feature.

Steps drive `cli.main()` with real argv — the assembled
argv→parser→registry→runner→named-exit loop the unit pins reach only
piecemeal. Per-command routing is pinned by distinct recording runners
patched onto each pipeline's `run` attribute: `create_registry()` still
resolves those attributes inside `main()`, so a wrong mapping would run a
different recorder. `collect` additionally runs for real against a fake
`requests` seam so the download→atomic-write loop is covered.
"""

import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fakes import FakeRequestsModule, RecordingRunner
from nyc_taxi_demand_forecasting.data import collection as collection_module
from nyc_taxi_demand_forecasting.interfaces import cli
from nyc_taxi_demand_forecasting.pipelines import (
    collect,
    deploy,
    evaluate,
    features,
    monitor,
    preprocess,
    train,
    tune,
)
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/pipelines_cli.feature")

_PIPELINE_MODULES = (
    collect,
    preprocess,
    features,
    train,
    tune,
    evaluate,
    deploy,
    monitor,
)


@dataclass
class CliRun:
    """State shared between the given/when/then steps of a scenario."""

    config_path: Path
    runners: dict[str, RecordingRunner] = field(default_factory=dict)
    fake_requests: FakeRequestsModule | None = None
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


@given("every pipeline's runner records its calls")
def _recording_runners(run: CliRun, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange — one recorder per pipeline `run` attribute; the registry
    # dict built inside main() resolves these attrs at dispatch time, so a
    # wrong mapping runs the wrong recorder.
    for module in _PIPELINE_MODULES:
        runner = RecordingRunner()
        run.runners[module.__name__.rsplit(".", 1)[-1]] = runner
        monkeypatch.setattr(module, "run", runner)


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


@given("the TLC endpoint serves parquet bytes")
def _tce_endpoint(run: CliRun, monkeypatch: pytest.MonkeyPatch) -> None:
    # Arrange — real collector, fake HTTP: the magic-checked payload still
    # flows through the atomic write.
    run.fake_requests = FakeRequestsModule(content=b"PAR1xxxxPAR1")
    monkeypatch.setattr(collection_module, "requests", run.fake_requests)


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
        [
            "nyc_taxi_demand_forecasting",
            command,
            "--config",
            str(run.config_path),
        ],
    )
    try:
        cli.main()
    except SystemExit as exc:
        run.exit_code = exc.code
    run.stderr = capsys.readouterr().err


@then(parsers.parse('only the "{command}" pipeline ran once'))
def _only_command_ran(run: CliRun, command: str) -> None:
    # Assert — routing identity: exactly the named recorder saw the call.
    for name, runner in run.runners.items():
        expected = [run.config_path] if name == command else []
        assert runner.calls == expected, name


@then(parsers.parse('the raw parquet for month "{month}" exists'))
def _raw_parquet_exists(run: CliRun, month: str) -> None:
    # Assert — paths.* resolve against the config's project root.
    expected = (
        run.config_path.parent.parent
        / "data"
        / "raw"
        / f"yellow_tripdata_{month}.parquet"
    )
    assert expected.is_file()


@then(parsers.parse('the collector fetched "{url}"'))
def _collector_fetched(run: CliRun, url: str) -> None:
    # Assert
    assert run.fake_requests is not None
    assert run.fake_requests.urls == [url]


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
