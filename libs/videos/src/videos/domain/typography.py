from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypographyPreset:
    title_size: int = 40
    subtitle_size: int = 22
    body_size: int = 24
    caption_size: int = 16
    bullet_size: int = 22
    code_size: int = 18


DEFAULT_TYPOGRAPHY = TypographyPreset()
