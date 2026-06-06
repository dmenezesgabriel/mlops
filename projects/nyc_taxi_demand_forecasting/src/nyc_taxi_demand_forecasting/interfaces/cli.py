import argparse
import logging
from pathlib import Path
from uuid import uuid4

from mlops_shared.logging import MlopsLoggingConfigurator
from mlops_shared.pipeline import PipelineCommandRegistry

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


def create_parser(
    registry: PipelineCommandRegistry | None = None,
) -> argparse.ArgumentParser:
    command_registry = registry or create_registry()
    parser = argparse.ArgumentParser(
        description="Run NYC taxi demand forecasting pipelines."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_name in command_registry.names():
        command_parser = subparsers.add_parser(command_name)
        command_parser.add_argument("--config", required=True)
    return parser


def create_registry() -> PipelineCommandRegistry:
    return PipelineCommandRegistry(
        {
            "collect": collect.run,
            "preprocess": preprocess.run,
            "features": features.run,
            "train": train.run,
            "tune": tune.run,
            "evaluate": evaluate.run,
            "deploy": deploy.run,
            "monitor": monitor.run,
        }
    )


def run_command(
    registry: PipelineCommandRegistry, command_name: str, config_path: Path
) -> None:
    logger = logging.getLogger("nyc_taxi_demand_forecasting.cli")
    context = {
        "command": command_name,
        "config_path": str(config_path),
        "correlation_id": uuid4().hex,
    }
    logger.info("pipeline_command_started", extra=context)
    try:
        registry.runner_for(command_name)(config_path)
    except Exception:
        logger.exception("pipeline_command_failed", extra=context)
        raise
    logger.info("pipeline_command_completed", extra=context)


def main() -> None:
    MlopsLoggingConfigurator().configure()
    registry = create_registry()
    arguments = create_parser(registry).parse_args()
    run_command(registry, arguments.command, Path(arguments.config))


if __name__ == "__main__":
    main()
