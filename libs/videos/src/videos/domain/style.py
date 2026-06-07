from __future__ import annotations

from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel


@dataclass(frozen=True)
class StyleSpec(PydanticModel):
    typography_preset: str = "default"
    color_palette: str = "default"
    spacing_scale: str = "default"
    render_profile: str = "default"
