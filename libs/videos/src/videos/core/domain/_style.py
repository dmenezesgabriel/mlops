from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleSpec:
    typography_preset: str = "default"
    color_palette: str = "default"
    spacing_scale: str = "default"
    render_profile: str = "default"
