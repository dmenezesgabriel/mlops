import logging
from pathlib import Path

from {{ cookiecutter.project_slug }}.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    """Execute the tune pipeline.

    Example:
        run(Path("configs/project.yaml"))
    """
    config = ProjectConfigLoader().load(config_path)
    logging.getLogger(__name__).info(
        "tune_pipeline_completed",
        extra={"models": str(config.paths.models)},
    )
