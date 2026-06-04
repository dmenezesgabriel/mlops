import logging

from mlops_shared.pipeline import PipelineStep


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
