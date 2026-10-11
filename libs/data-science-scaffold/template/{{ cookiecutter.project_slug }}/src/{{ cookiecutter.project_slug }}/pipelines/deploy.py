from pathlib import Path

from {{ cookiecutter.project_slug }}.configuration import ProjectConfigLoader


def run(config_path: Path) -> None:
    """Execute the deploy pipeline.

    Example:
        run(Path("configs/project.yaml"))
    """
    ProjectConfigLoader().load(config_path)
    raise NotImplementedError("deploy pipeline is not implemented")
