"""Register a scaffolded project into the root monorepo pyproject.toml.

Usage:
    python -m data_science_scaffold.register <project_slug>

Adds the project slug to the uv workspace members, deptry known_first_party,
importlinter root_packages, and every forbidden_modules contract that already
guards against project imports. Idempotent: rerunning is a no-op. A drifted
pyproject — a missing section, list, or anchor element — raises RuntimeError
instead of being silently under-registered.

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
_MODULE_ANCHOR = "nyc_taxi_demand_forecasting"
_MEMBER_ANCHOR = f"projects/{_MODULE_ANCHOR}"
_SECTION_BREAK = re.compile(r"(?m)^\[")
_CONTRACT_BLOCK = re.compile(
    r"(?ms)^\[\[tool\.importlinter\.contracts\]\][^\n]*\n.*?(?=^\[|\Z)"
)

# (TOML section header, list key, anchor element, element prefix) — the
# element added after the anchor is prefix + slug.
_REQUIRED_LISTS: tuple[tuple[str, str, str, str], ...] = (
    ("tool.uv.workspace", "members", _MEMBER_ANCHOR, "projects/"),
    ("tool.deptry", "known_first_party", _MODULE_ANCHOR, ""),
    ("tool.importlinter", "root_packages", _MODULE_ANCHOR, ""),
)


def register_project(slug: str, pyproject_path: Path = PYPROJECT_PATH) -> bool:
    """Register slug into pyproject lists; return True if anything changed.

    Example:
        register_project("my_project", Path("pyproject.toml"))
    """
    _validate_slug(slug)
    text = pyproject_path.read_text(encoding="utf-8")
    updated = text
    for section, key, anchor, prefix in _REQUIRED_LISTS:
        updated = _extend_required_list(
            updated, section, key, anchor, prefix + slug
        )
    updated = _extend_forbidden_contracts(updated, slug)

    if updated == text:
        return False

    _assert_valid_toml(updated)
    pyproject_path.write_text(updated, encoding="utf-8")
    return True


def _extend_required_list(
    text: str, section: str, key: str, anchor: str, element: str
) -> str:
    """Add `"element"` after `"anchor"` inside `[section]`'s `key` list.

    A list already containing the element anywhere is left alone; a missing
    section, list, or anchor element means the pyproject drifted and must
    not be written.
    """
    start, end = _section_span(text, section)
    array = _find_array(text, key, start, end)
    if f'"{element}"' in array.group(0):
        return text
    if f'"{anchor}"' not in array.group(0):
        raise RuntimeError(
            f'anchor "{anchor}" not found in [{section}] {key}; expected '
            f'the "{anchor}" element to locate the insertion point'
        )
    spliced = _insert_after_anchor(array.group(0), anchor, element)
    return text[: array.start()] + spliced + text[array.end() :]


def _section_span(text: str, header: str) -> tuple[int, int]:
    """Return `(start, end)` of `[header]`'s body — the next `[`-line ends it."""
    match = re.search(rf"(?m)^\[{re.escape(header)}\][ \t]*$", text)
    if match is None:
        raise RuntimeError(
            f"section [{header}] not found in pyproject.toml; expected "
            f"a [{header}] table for project registration"
        )
    following = _SECTION_BREAK.search(text, match.end())
    return match.end(), following.start() if following else len(text)


def _find_array(text: str, key: str, start: int, end: int) -> re.Match[str]:
    """Match `key = [...]` — single- or multi-line — inside text[start:end]."""
    match = re.compile(rf"(?ms)^[ \t]*{re.escape(key)}\s*=\s*\[.*?\]").search(
        text, start, end
    )
    if match is None:
        raise RuntimeError(
            f"{key} list not found in pyproject.toml; expected a "
            f"`{key} = [...]` array for project registration"
        )
    return match


def _insert_after_anchor(array_text: str, anchor: str, element: str) -> str:
    """Splice `"element"` directly after `"anchor"` in a TOML array literal.

    An anchor on its own line gets a matching-indent element line; an
    inline anchor gets `"anchor", "element"`.
    """
    own_line = re.search(
        rf'(?m)^([ \t]*)"{re.escape(anchor)}"(,?)[ \t]*\n', array_text
    )
    if own_line is None:
        return array_text.replace(f'"{anchor}"', f'"{anchor}", "{element}"', 1)
    indent = own_line.group(1)
    addition = f'{indent}"{anchor}",\n{indent}"{element}",\n'
    return (
        array_text[: own_line.start()]
        + addition
        + array_text[own_line.end() :]
    )


def _extend_forbidden_contracts(text: str, slug: str) -> str:
    """Append `"slug"` to each contract's forbidden_modules that guards
    project imports — identified by listing the anchor module."""
    anchored = 0

    def _extend(match: re.Match[str]) -> str:
        nonlocal anchored
        block = match.group(0)
        array = re.search(r"(?s)forbidden_modules\s*=\s*\[.*?\]", block)
        if array is None or f'"{_MODULE_ANCHOR}"' not in array.group(0):
            return block
        anchored += 1
        if f'"{slug}"' in array.group(0):
            return block
        spliced = _insert_after_anchor(array.group(0), _MODULE_ANCHOR, slug)
        return block[: array.start()] + spliced + block[array.end() :]

    updated = _CONTRACT_BLOCK.sub(_extend, text)
    if anchored == 0:
        raise RuntimeError(
            f'no forbidden_modules list contains "{_MODULE_ANCHOR}"; '
            "expected at least one import-linter contract guarding "
            "project imports"
        )
    return updated


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
