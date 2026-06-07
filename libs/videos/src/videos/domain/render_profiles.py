from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderProfile:
    name: str
    quality: str
    frame_rate: int = 30
    resolution: tuple[int, int] = (1920, 1080)


PREVIEW = RenderProfile(
    name="preview",
    quality="low",
    frame_rate=15,
    resolution=(854, 480),
)

FINAL = RenderProfile(
    name="final",
    quality="high",
    frame_rate=30,
    resolution=(1920, 1080),
)

BUILT_IN_PROFILES: dict[str, RenderProfile] = {
    p.name: p for p in [PREVIEW, FINAL]
}
