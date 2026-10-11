from pathlib import Path

from {{ cookiecutter.project_slug }}.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    """Execute the tune pipeline.

    Example:
        run(Path("configs/project.yaml"))
    """
    ProjectConfigLoader().load(config_path)
    raise NotImplementedError("tune pipeline is not implemented")
