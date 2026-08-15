"""Render the data-science cookiecutter template into an output directory."""

from pathlib import Path

from cookiecutter.main import cookiecutter

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template"


def generate(slug: str, output_dir: str | Path) -> Path:
    """Render the cookiecutter template for slug under output_dir.

    Example:
        generate("my_project", Path("projects"))
    """
    rendered_path = cookiecutter(
        template=str(TEMPLATE_DIR),
        output_dir=str(output_dir),
        no_input=True,
        extra_context={"project_slug": slug},
    )
    return Path(rendered_path)
