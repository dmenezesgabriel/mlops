"""Register a scaffolded project into the root monorepo pyproject.toml.

Usage:
    python -m data_science_scaffold.register <project_slug>

Adds the project slug to the uv workspace members, deptry known_first_party,
importlinter root_packages, and every forbidden_modules contract that already
guards against project imports. Idempotent: rerunning is a no-op.

Example:
    python -m data_science_scaffold.register nyc_taxi_demand_forecasting
"""

import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_MEMBER_ANCHOR = '  "projects/nyc_taxi_demand_forecasting",\n'
_MODULE_ANCHOR = '  "nyc_taxi_demand_forecasting",\n'


def register_project(slug: str, pyproject_path: Path = PYPROJECT_PATH) -> bool:
    """Register slug into pyproject lists; return True if anything changed."""
    _validate_slug(slug)
    text = pyproject_path.read_text(encoding="utf-8")
    updated = _insert_after_members(text, slug)
    updated = _insert_after_first_party_modules(updated, slug)
    updated = _extend_forbidden_contracts(updated, slug)

    if updated == text:
        return False

    _assert_valid_toml(updated)
    pyproject_path.write_text(updated, encoding="utf-8")
    return True


def _insert_after_members(text: str, slug: str) -> str:
    addition = f'  "projects/{slug}",\n'
    pattern = re.compile(
        re.escape(_MEMBER_ANCHOR) + "(?!" + re.escape(addition) + ")"
    )
    return pattern.sub(_MEMBER_ANCHOR + addition, text)


def _insert_after_first_party_modules(text: str, slug: str) -> str:
    addition = f'  "{slug}",\n'
    pattern = re.compile(
        re.escape(_MODULE_ANCHOR) + "(?!" + re.escape(addition) + ")"
    )
    return pattern.sub(_MODULE_ANCHOR + addition, text)


def _extend_forbidden_contracts(text: str, slug: str) -> str:
    quoted_slug = f'"{slug}"'
    pattern = re.compile(
        r'forbidden_modules = \[[^\]\n]*"nyc_taxi_demand_forecasting"[^\]\n]*\]'
    )

    def _extend(match: re.Match[str]) -> str:
        if quoted_slug in match.group(0):
            return match.group(0)
        return match.group(0)[:-1] + f", {quoted_slug}]"

    return pattern.sub(_extend, text)


def _validate_slug(slug: str) -> None:
    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            f"Invalid project slug {slug!r}: expected lowercase "
            "letters, digits, and underscores starting with a letter"
        )


def _assert_valid_toml(text: str) -> None:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(
            "pyproject.toml is no longer valid TOML after registering"
        ) from exc


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python scripts/register_project.py <project_slug>"
        )
    changed = register_project(sys.argv[1])
    if changed:
        print(f"Registered {sys.argv[1]} in pyproject.toml")
    else:
        print(f"{sys.argv[1]} is already registered in pyproject.toml")


if __name__ == "__main__":
    main()
