import logging
from pathlib import Path

import pytest
from mlops_shared.pipeline import PipelineCommandRegistry, PipelineStep


class SpyPipelineStep(PipelineStep):
    def __init__(self, logger: logging.Logger) -> None:
        super().__init__(logger)
        self.was_run = False

    @property
    def name(self) -> str:
        return "spy_step"

    def _run_step(self) -> None:
        self.was_run = True


def test_pipeline_step_runs_template_method() -> None:
    # Arrange
    step = SpyPipelineStep(logging.getLogger("test_pipeline_step"))

    # Act
    step.run()

    # Assert
    assert step.was_run is True


def test_pipeline_command_registry_returns_runner() -> None:
    # Arrange
    config_paths: list[Path] = []

    def run_pipeline(config_path: Path) -> None:
        config_paths.append(config_path)

    registry = PipelineCommandRegistry({"train": run_pipeline})

    # Act
    registry.runner_for("train")(Path("project.yaml"))

    # Assert
    assert config_paths == [Path("project.yaml")]


def test_pipeline_command_registry_reports_invalid_command() -> None:
    # Arrange
    registry = PipelineCommandRegistry({"train": lambda config_path: None})

    # Act / Assert
    with pytest.raises(ValueError, match="Invalid pipeline command evaluate"):
        registry.runner_for("evaluate")
