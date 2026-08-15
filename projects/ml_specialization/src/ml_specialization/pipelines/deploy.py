import logging
from pathlib import Path

from ml_specialization.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    """Execute the deploy pipeline.

    Example:
        run(Path("configs/project.yaml"))
    """
    config = ProjectConfigLoader().load(config_path)
    logging.getLogger(__name__).info(
        "deploy_pipeline_completed",
        extra={"model_name": config.mlflow.registered_model_name},
    )
