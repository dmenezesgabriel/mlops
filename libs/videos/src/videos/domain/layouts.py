from __future__ import annotations

from dataclasses import dataclass

from videos.domain.layout import LayoutRegion, LayoutSpec


@dataclass(frozen=True)
class LayoutPreset:
    name: str
    layout: LayoutSpec


TITLE_ONLY = LayoutPreset(
    name="title_only",
    layout=LayoutSpec(regions=(LayoutRegion.TITLE,)),
)

TITLE_AND_BODY = LayoutPreset(
    name="title_and_body",
    layout=LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.BODY)),
)

DIAGRAM_WITH_LABELS = LayoutPreset(
    name="diagram_with_labels",
    layout=LayoutSpec(
        regions=(
            LayoutRegion.TITLE,
            LayoutRegion.DIAGRAM,
            LayoutRegion.FOOTER,
        )
    ),
)

COMPARISON = LayoutPreset(
    name="comparison",
    layout=LayoutSpec(
        regions=(
            LayoutRegion.TITLE,
            LayoutRegion.LEFT_PANEL,
            LayoutRegion.RIGHT_PANEL,
            LayoutRegion.FOOTER,
        )
    ),
)

FULL_FRAME = LayoutPreset(
    name="full_frame",
    layout=LayoutSpec(
        regions=(
            LayoutRegion.TITLE,
            LayoutRegion.BODY,
            LayoutRegion.DIAGRAM,
            LayoutRegion.EQUATION,
            LayoutRegion.FOOTER,
        )
    ),
)

BUILT_IN_LAYOUTS: dict[str, LayoutPreset] = {
    p.name: p
    for p in [
        TITLE_ONLY,
        TITLE_AND_BODY,
        DIAGRAM_WITH_LABELS,
        COMPARISON,
        FULL_FRAME,
    ]
}
