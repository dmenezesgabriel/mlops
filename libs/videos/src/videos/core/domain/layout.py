from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


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
class LayoutSpec:
    regions: tuple[LayoutRegion, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for r in self.regions:
            if r.value in seen:
                raise ValueError(f"Duplicate region in LayoutSpec: {r.value}")
            seen.add(r.value)

    @property
    def region_names(self) -> frozenset[str]:
        return frozenset(r.value for r in self.regions)
