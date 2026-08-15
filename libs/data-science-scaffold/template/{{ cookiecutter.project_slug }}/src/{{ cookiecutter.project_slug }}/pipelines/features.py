import logging
from pathlib import Path

from {{ cookiecutter.project_slug }}.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    """Execute the features pipeline.

    Example:
        run(Path("configs/project.yaml"))
    """
    config = ProjectConfigLoader().load(config_path)
    logging.getLogger(__name__).info(
        "features_pipeline_completed",
        extra={"training_dataset": str(config.features.training_dataset_path)},
    )
