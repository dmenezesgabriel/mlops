from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim import Scene, VGroup


def build_cycle_nodes(
    scene: Scene,
    labels: Sequence[str],
    colors: Sequence[str],
    radius: float = 0.6,
) -> VGroup:
    import math

    from manim import Circle, Text, VGroup

    n = len(labels)
    nodes = VGroup()
    for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
        angle = 2 * math.pi * index / n - math.pi / 2
        x = 2.5 * math.cos(angle)
        y = 2.5 * math.sin(angle)
        circle = Circle(radius=radius, color=color, fill_opacity=0.2).move_to([x, y, 0])
        text = Text(label, font_size=18).move_to(circle.get_center())
        nodes.add(VGroup(circle, text))
    return nodes


def build_linear_nodes(
    scene: Scene,
    labels: Sequence[str],
    colors: Sequence[str],
) -> VGroup:
    from manim import RIGHT, Circle, Text, VGroup

    nodes = VGroup()
    for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
        circle = Circle(radius=0.5, color=color, fill_opacity=0.2)
        circle.shift(2.0 * index * RIGHT)
        text = Text(label, font_size=16).move_to(circle.get_center())
        nodes.add(VGroup(circle, text))
    return nodes


def create_target(
    scene: Scene,
    rings: int = 4,
    max_radius: float = 2.0,
) -> VGroup:
    from manim import Circle, VGroup

    target = VGroup()
    ring_colors = ("#FF0000", "#FFFFFF", "#FF0000", "#FFFFFF")
    for index in range(rings, 0, -1):
        r = max_radius * index / rings
        color = ring_colors[index % len(ring_colors)]
        circle = Circle(radius=r, color=color, stroke_width=3, fill_opacity=0.3)
        target.add(circle)
    return target
