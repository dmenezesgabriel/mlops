"""In-package import convention: domain symbols are imported from their
canonical `entities`/`value_objects` modules, never via the flat
`videos.domain.<name>` re-export shims (which exist only for out-of-package
consumers like `videos_linter`). The same convention applies to
`videos.application.quality_gate` vs `videos.application.use_cases.quality_gate`.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

from videos.application.use_cases.quality_gate import (
    QualityGate as UseCaseQualityGate,
)

_PKG_ROOT = Path(__file__).resolve().parents[4]
_SRC_ROOT = _PKG_ROOT / "src" / "videos"
_TESTS_ROOT = _PKG_ROOT / "tests"

_SHIM_MODULE_NAMES = frozenset(
    {
        "concept",
        "concept_extension",
        "concept_registry",
        "identifiers",
        "layout",
        "narrative",
        "quality",
        "scene_spec",
        "storyboard",
        "style",
        "timeline",
    }
)

_FLAT_DOMAIN_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+videos\.domain\."
    r"(?:" + "|".join(sorted(_SHIM_MODULE_NAMES)) + r")\b",
    re.MULTILINE,
)
_FLAT_QUALITY_GATE_IMPORT = re.compile(
    r"^\s*from\s+videos\.application\.quality_gate\s+import\b",
    re.MULTILINE,
)


def _is_shim_module(path: Path) -> bool:
    if path.parent.name == "domain":
        return path.stem in _SHIM_MODULE_NAMES
    return path.parent.name == "application" and path.name == "quality_gate.py"


def _offending_modules(root: Path) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if _is_shim_module(path):
            continue
        content = path.read_text()
        if _FLAT_DOMAIN_IMPORT.search(content) or (
            _FLAT_QUALITY_GATE_IMPORT.search(content)
        ):
            offenders.append(str(path.relative_to(root)))
    return offenders


class TestCanonicalImports:
    def test_src_modules_import_domain_symbols_canonically(self) -> None:
        assert _offending_modules(_SRC_ROOT) == []

    def test_tests_import_domain_symbols_canonically(self) -> None:
        assert _offending_modules(_TESTS_ROOT) == []

    def test_shim_modules_still_re_export_for_external_consumers(self) -> None:
        # The flat modules are the published compat surface — deleting one,
        # or letting its re-export drift from `__all__`, is an API break
        # for out-of-package importers such as `videos_linter`.
        domain_dir = _SRC_ROOT / "domain"
        for name in sorted(_SHIM_MODULE_NAMES):
            assert (domain_dir / f"{name}.py").is_file(), name
        assert (_SRC_ROOT / "application" / "quality_gate.py").is_file()

    def test_shim_modules_resolve_every_exported_name(self) -> None:
        for name in sorted(_SHIM_MODULE_NAMES):
            module = importlib.import_module(f"videos.domain.{name}")
            missing = [n for n in module.__all__ if not hasattr(module, n)]
            assert missing == [], f"{name}: {missing}"
        gate = importlib.import_module("videos.application.quality_gate")
        assert gate.QualityGate is UseCaseQualityGate
