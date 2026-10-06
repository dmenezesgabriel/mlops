from pathlib import Path

from ml_specialization.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    """Execute the preprocess pipeline.

    Example:
        run(Path("configs/project.yaml"))
    """
    ProjectConfigLoader().load(config_path)
    raise NotImplementedError("preprocess pipeline is not implemented")
