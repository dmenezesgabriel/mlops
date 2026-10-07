"""Gate-wiring conformance for this package — runs under root pytest.

The parity glue is real code with a real unit suite; it must sit inside the
repo's per-package gate loop (root ``PACKAGES``) with the same local recipes
and tool config the sibling packages carry. These assertions pin that
wiring so a future exclusion fails a test instead of slipping silently.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT = PROJECT_DIR.parents[1]


def test_package_is_in_root_packages_loop() -> None:
    makefile = (ROOT / "Makefile").read_text()
    packages = re.search(r"^PACKAGES = (.+)$", makefile, re.MULTILINE)
    assert packages is not None
    assert "projects/athena_emulator" in packages.group(1).split()


def test_makefile_quality_chains_the_sibling_gates() -> None:
    recipes = (PROJECT_DIR / "Makefile").read_text()
    quality = re.search(r"^quality: (.+)$", recipes, re.MULTILINE)
    assert quality is not None
    assert set(quality.group(1).split()) == {
        "lint",
        "type-check",
        "test",
        "coverage",
        "complexity",
        "dependencies",
        "security",
        "maintainability",
    }


def test_pyproject_declares_gate_config() -> None:
    pyproject = tomllib.loads((PROJECT_DIR / "pyproject.toml").read_text())
    assert pyproject["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]
    assert pyproject["tool"]["coverage"]["run"]["source"] == [
        "notebooks",
        "tests",
    ]
    assert pyproject["tool"]["pyright"]["typeCheckingMode"] == "strict"
