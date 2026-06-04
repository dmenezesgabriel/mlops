from abc import ABC, abstractmethod
from logging import Logger


class PipelineStep(ABC):
    """Template method for observable, reproducible pipeline steps.

    Example:
        MyStep(logger).run()
    """

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def run(self) -> None:
        self._logger.info("pipeline_step_started", extra={"step": self.name})
        self._run_step()
        self._logger.info("pipeline_step_completed", extra={"step": self.name})

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def _run_step(self) -> None:
        pass
