import re
import sys
from pathlib import Path

SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def main() -> None:
    project_slug = "{{ cookiecutter.project_slug }}"
    if not SLUG_PATTERN.fullmatch(project_slug):
        sys.exit(
            f"Invalid project_slug {project_slug!r}: "
            "expected lowercase letters, digits, and underscores"
        )

    project_dir = Path.cwd() / "projects" / project_slug
    if project_dir.exists():
        sys.exit(f"projects/{project_slug} already exists")


if __name__ == "__main__":
    main()
