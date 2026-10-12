"""Step definitions for the monitor-pipeline BDD feature.

Steps drive `cli.main()` argv `monitor --config` — the assembled
argv→registry→`monitor.run`→report-file loop the Makefile `monitor`
recipe invokes. Only the MLflow boundary is faked (`monitor.mlflow` /
`monitor.MlflowClient` module attrs, the same seams the unit pins use);
the config load, parquet read, drift analysis, and report write run for
real under `tmp_path`.
"""

import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import pytest
from fakes import (
    FakeMlflowClient,
    FakeMlflowModule,
    FakeModelVersion,
    training_frame,
)
from nyc_taxi_demand_forecasting.interfaces import cli
from nyc_taxi_demand_forecasting.pipelines import monitor as monitor_module
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("features/monitor.feature")


@dataclass
class MonitorRun:
    """State shared between the given/when/then steps of a scenario."""

    config_path: Path
    project_root: Path
    fake_mlflow: FakeMlflowModule = field(default_factory=FakeMlflowModule)
    exit_code: int | str | None = 0
    stderr: str = ""
    report: str = ""


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
def run(tmp_path: Path) -> MonitorRun:
    return MonitorRun(
        config_path=tmp_path / "configs" / "project.yaml",
        project_root=tmp_path,
    )


@given("a monitor project config exists")
def _monitor_config(run: MonitorRun, project_config_yaml: str) -> None:
    # Arrange
    run.config_path.parent.mkdir(parents=True)
    run.config_path.write_text(project_config_yaml, encoding="utf-8")


@given("a training dataset exists")
def _training_dataset(run: MonitorRun) -> None:
    # Arrange — the resolved path mirrors `features.training_dataset_path`.
    dataset_path = (
        run.project_root / "data" / "processed" / "training_dataset.parquet"
    )
    dataset_path.parent.mkdir(parents=True)
    training_frame().to_parquet(dataset_path, index=False)


@given(
    parsers.parse(
        'the registry promotes champion version "{version}" of "{model_name}"'
    )
)
def _champion_registry(
    run: MonitorRun,
    version: str,
    model_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange — alias hit: the monitor loads `models:/<name>@champion`.
    monkeypatch.setattr(monitor_module, "mlflow", run.fake_mlflow)
    monkeypatch.setattr(
        monitor_module,
        "MlflowClient",
        partial(
            FakeMlflowClient,
            alias_versions={
                (model_name, "champion"): FakeModelVersion(version)
            },
        ),
    )


@given(parsers.parse('the registry holds no versions of "{model_name}"'))
def _empty_registry(
    run: MonitorRun, model_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange — no alias and no versions: the alias lookup raises, the
    # latest-version fallback then finds an empty page.
    monkeypatch.setattr(monitor_module, "mlflow", run.fake_mlflow)
    monkeypatch.setattr(monitor_module, "MlflowClient", FakeMlflowClient)


@when("I run the monitor pipeline")
def _run_monitor(
    run: MonitorRun,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Act
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nyc_taxi_demand_forecasting",
            "monitor",
            "--config",
            str(run.config_path),
        ],
    )
    try:
        cli.main()
    except SystemExit as exc:
        run.exit_code = exc.code
    run.stderr = capsys.readouterr().err


@then("the monitoring report exists")
def _report_exists(run: MonitorRun) -> None:
    # Assert — stash the text so content steps assert against one read.
    report_path = run.project_root / "reports" / "monitoring.md"
    assert report_path.is_file()
    run.report = report_path.read_text(encoding="utf-8")


@then("no monitoring report exists")
def _no_report(run: MonitorRun) -> None:
    # Assert — a failed run must not leave a half-written report behind.
    report_path = run.project_root / "reports" / "monitoring.md"
    assert not report_path.exists()


@then(
    parsers.parse(
        'the report names champion version "{version}" with alias "{alias}"'
    )
)
def _report_identity(run: MonitorRun, version: str, alias: str) -> None:
    # Assert — the report must name the model it actually evaluated.
    assert f"Version: `{version}`" in run.report
    assert f"Alias: `{alias}`" in run.report


@then(parsers.parse('the report marks "{status}"'))
def _report_status(run: MonitorRun, status: str) -> None:
    # Assert — the ~12% simulated pickup shift must surface as drift.
    assert status in run.report


@then(parsers.parse('the monitor run exits reporting "{message}"'))
def _monitor_exit_message(run: MonitorRun, message: str) -> None:
    # Assert
    assert isinstance(run.exit_code, str)
    assert message in run.exit_code


@then(parsers.parse('the monitor run logged "{event}"'))
def _monitor_logged(run: MonitorRun, event: str) -> None:
    # Assert
    assert event in run.stderr


@then(parsers.parse('the monitor run did not log "{event}"'))
def _monitor_not_logged(run: MonitorRun, event: str) -> None:
    # Assert
    assert event not in run.stderr
