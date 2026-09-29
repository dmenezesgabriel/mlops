"""Render the data-science cookiecutter template into an output directory.

Usage:
    python -m data_science_scaffold.scaffold <project_slug>

Renders into the repo's ``projects/`` directory using the workspace-pinned
cookiecutter engine. Operator-facing failures (invalid slug, existing
project dir) exit cleanly with the error message instead of a traceback.

Example:
    python -m data_science_scaffold.scaffold nyc_taxi_demand_forecasting
"""

# pyright: reportMissingTypeStubs=false
# cookiecutter ships no type stubs; the line-level ignore cannot survive
# ruff's 79-col import split, so the rule is scoped off for this file.

import sys
from pathlib import Path

from cookiecutter.exceptions import (
    FailedHookException,
    OutputDirExistsException,
)
from cookiecutter.main import cookiecutter

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "template"
REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECTS_DIR = REPO_ROOT / "projects"


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


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m data_science_scaffold.scaffold <project_slug>"
        )
    try:
        rendered = generate(sys.argv[1], PROJECTS_DIR)
    except (FailedHookException, OutputDirExistsException) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Rendered {rendered}")


if __name__ == "__main__":
    main()
