from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrandColors:
    primary: str = "#4A90D9"
    secondary: str = "#50C878"
    accent: str = "#FF8C42"
    danger: str = "#E74C3C"
    warning: str = "#FFD700"
    background: str = "#1e1e1e"
    text_primary: str = "#FFFFFF"
    text_secondary: str = "#CCCCCC"


DEFAULT_BRAND = BrandColors()
