import argparse
from collections.abc import Callable
from pathlib import Path

from mlops_shared.logging import MlopsLoggingConfigurator

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

PipelineRunner = Callable[[Path], None]


class PipelineCommandRegistry:
    """Map CLI command names to pipeline entrypoints.

    Example:
        PipelineCommandRegistry().runner_for("collect")
    """

    def __init__(self) -> None:
        self._runners: dict[str, PipelineRunner] = {
            "collect": collect.run,
            "preprocess": preprocess.run,
            "features": features.run,
            "train": train.run,
            "tune": tune.run,
            "evaluate": evaluate.run,
            "deploy": deploy.run,
            "monitor": monitor.run,
        }

    def runner_for(self, command_name: str) -> PipelineRunner:
        runner = self._runners.get(command_name)
        if runner is not None:
            return runner

        raise ValueError(f"Invalid pipeline command {command_name}: expected one of {self.names()}")

    def names(self) -> tuple[str, ...]:
        return tuple(self._runners)


def create_parser(registry: PipelineCommandRegistry | None = None) -> argparse.ArgumentParser:
    command_registry = registry or PipelineCommandRegistry()
    parser = argparse.ArgumentParser(description="Run NYC taxi demand forecasting pipelines.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in command_registry.names():
        command_parser = subparsers.add_parser(command_name)
        command_parser.add_argument("--config", required=True)
    return parser


def main() -> None:
    MlopsLoggingConfigurator().configure()
    registry = PipelineCommandRegistry()
    arguments = create_parser(registry).parse_args()
    registry.runner_for(arguments.command)(Path(arguments.config))


if __name__ == "__main__":
    main()
