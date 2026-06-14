from __future__ import annotations

from dataclasses import dataclass

from videos.domain.layout import LayoutRegion, LayoutSpec
from videos.domain.scene_spec import ComponentSpec, SceneSpec


@dataclass(frozen=True)
class LayoutRegionCoordinates:
    x: float
    y: float
    z: float

    def to_list(self) -> list[float]:
        return [self.x, self.y, self.z]


class ManimLayoutEngine:
    # Default coordinates for regions in Manim units
    REGION_MAP = {
        LayoutRegion.TITLE: LayoutRegionCoordinates(0, 3, 0),
        LayoutRegion.BODY: LayoutRegionCoordinates(0, 0, 0),
        LayoutRegion.DIAGRAM: LayoutRegionCoordinates(0, -1, 0),
        LayoutRegion.LEFT_PANEL: LayoutRegionCoordinates(-3, 0, 0),
        LayoutRegion.RIGHT_PANEL: LayoutRegionCoordinates(3, 0, 0),
        LayoutRegion.FOOTER: LayoutRegionCoordinates(0, -3.5, 0),
        LayoutRegion.EQUATION: LayoutRegionCoordinates(0, -2, 0),
        LayoutRegion.CALLOUT: LayoutRegionCoordinates(4, 2, 0),
    }

    def apply(self, scene: SceneSpec) -> SceneSpec:
        if not scene.components:
            return scene

        new_components = []
        region_counts: dict[LayoutRegion, int] = {}
        for comp in scene.components:
            region = LayoutRegion(comp.region)
            coords = self.REGION_MAP.get(
                region, LayoutRegionCoordinates(0, 0, 0)
            )
            count = region_counts.get(region, 0)
            region_counts[region] = count + 1

            new_props = dict(comp.props)
            offset_y = coords.y - 0.8 * count
            new_props["position"] = [
                float(coords.x),
                float(offset_y),
                float(coords.z),
            ]

            new_comp = ComponentSpec(
                type=comp.type,
                region=comp.region,
                props=new_props,
            )
            new_components.append(new_comp)

        return SceneSpec(
            scene_id=scene.scene_id,
            title=scene.title,
            goal=scene.goal,
            duration_seconds=scene.duration_seconds,
            layout=scene.layout,
            visual_objects=scene.visual_objects,
            timeline=scene.timeline,
            style=scene.style,
            components=tuple(new_components),
        )

    def validate_placement(self, layout: LayoutSpec) -> list[str]:
        return []
