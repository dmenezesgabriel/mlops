from abc import ABC, abstractmethod
from collections.abc import Callable
from logging import Logger
from pathlib import Path

PipelineCommandRunner = Callable[[Path], None]


class PipelineCommandRegistry:
    """Map CLI command names to project pipeline entrypoints.

    Example:
        PipelineCommandRegistry({"train": train}).runner_for("train")
    """

    def __init__(self, runners: dict[str, PipelineCommandRunner]) -> None:
        self._runners = dict(runners)

    def runner_for(self, command_name: str) -> PipelineCommandRunner:
        runner = self._runners.get(command_name)
        if runner is not None:
            return runner

        raise ValueError(f"Invalid pipeline command {command_name}: expected one of {self.names()}")

    def names(self) -> tuple[str, ...]:
        return tuple(self._runners)


class PipelineStep(ABC):
    """Template method for observable, reproducible pipeline steps.

    Example:
        MyStep(logger).run()
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def run(self) -> None:
        self._logger.info("pipeline_step_started", extra={"step": self.name})
        try:
            self._run_step()
        except Exception:
            self._logger.exception("pipeline_step_failed", extra={"step": self.name})
            raise
        self._logger.info("pipeline_step_completed", extra={"step": self.name})

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def _run_step(self) -> None:
        pass
