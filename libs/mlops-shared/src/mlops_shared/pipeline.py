from collections.abc import Callable
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

        raise ValueError(
            f"Invalid pipeline command {command_name}: expected one of {self.names()}"
        )

    def names(self) -> tuple[str, ...]:
        return tuple(self._runners)
