from pathlib import Path

import pytest
from mlops_shared.pipeline import PipelineCommandRegistry


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
