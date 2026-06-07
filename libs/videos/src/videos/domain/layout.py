from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator
from pydantic.dataclasses import dataclass

from videos.domain._base import PydanticModel


class LayoutRegion(StrEnum):
    TITLE = "title"
    BODY = "body"
    LEFT_PANEL = "left_panel"
    RIGHT_PANEL = "right_panel"
    DIAGRAM = "diagram"
    EQUATION = "equation"
    FOOTER = "footer"
    CALLOUT = "callout"

    @classmethod
    def all_region_names(cls) -> frozenset[str]:
        return frozenset(m.value for m in cls)


@dataclass(frozen=True)
class LayoutSpec(PydanticModel):
    regions: tuple[LayoutRegion, ...] = ()

    @model_validator(mode="after")
    def _no_duplicate_regions(self) -> LayoutSpec:
        seen: set[str] = set()
        for r in self.regions:
            if r.value in seen:
                raise ValueError(f"Duplicate region in LayoutSpec: {r.value}")
            seen.add(r.value)
        return self

    @property
    def region_names(self) -> frozenset[str]:
        return frozenset(r.value for r in self.regions)
