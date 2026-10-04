# pyright: reportMissingModuleSource=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# manim is an optional extra installed only in the render container and
# ships no type information; this module is the adapters' boundary to it.
"""Guard for the optional `manim` extra — name the missing dependency at the
port boundary instead of leaking a bare `ModuleNotFoundError` from whichever
call hits it first."""

from __future__ import annotations

import importlib


def require_manim() -> None:
    """Raise a named error when the `videos[manim]` extra is not installed.

    Example: `require_manim()` at the top of `ManimRenderer.render`.
    """
    try:
        importlib.import_module("manim")
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency 'manim': expected the videos[manim] extra"
            " installed"
        ) from exc
