from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from videos.application.components import ComponentRegistry
from videos.domain.scene_spec import ComponentSpec

if TYPE_CHECKING:
    from manim import Scene, VGroup


def build_cycle_nodes(
    scene: Scene,
    labels: Sequence[str],
    colors: Sequence[str],
    radius: float = 0.6,
) -> VGroup:
    import itertools
    import math

    from manim import Circle, Text, VGroup

    n = len(labels)
    if n == 0:
        return VGroup()

    colors = list(itertools.islice(itertools.cycle(colors), n))
    nodes = VGroup()
    for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
        angle = 2 * math.pi * index / n - math.pi / 2
        x = 2.5 * math.cos(angle)
        y = 2.5 * math.sin(angle)
        circle = Circle(radius=radius, color=color, fill_opacity=0.2).move_to(
            [x, y, 0]
        )
        text = Text(label, font_size=18).move_to(circle.get_center())
        nodes.add(VGroup(circle, text))
    return nodes


def build_linear_nodes(
    scene: Scene,
    labels: Sequence[str],
    colors: Sequence[str],
) -> VGroup:
    import itertools

    from manim import RIGHT, Circle, Text, VGroup

    n = len(labels)
    if n == 0:
        return VGroup()

    colors = list(itertools.islice(itertools.cycle(colors), n))
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
        circle = Circle(
            radius=r, color=color, stroke_width=3, fill_opacity=0.3
        )
        target.add(circle)
    return target


class TitleComponent:
    def build(self, spec: ComponentSpec, scene: object) -> Any:
        from manim import Scene, Text, Write

        content = str(spec.props.get("content", spec.region))
        text = Text(content, font_size=40)

        position = spec.props.get("position")
        if position:
            text.move_to(cast(Sequence[float], position))

        cast(Scene, scene).play(Write(text))
        return text


class TextComponent:
    def build(self, spec: ComponentSpec, scene: object) -> Any:
        from manim import Scene, Text, Write

        content = str(spec.props.get("content", ""))
        text = Text(content, font_size=24)

        position = spec.props.get("position")
        if position:
            text.move_to(cast(Sequence[float], position))

        cast(Scene, scene).play(Write(text))
        return text


class DiagramComponent:
    def build(self, spec: ComponentSpec, scene: object) -> Any:
        from manim import Scene, Write

        kind = str(spec.props.get("kind", "cycle"))
        labels = cast(list[str], spec.props.get("labels", []))
        colors = cast(
            list[str],
            spec.props.get(
                "colors",
                ["#4A90D9", "#E67E22", "#2ECC71", "#E74C3C", "#9B59B6"],
            ),
        )

        if kind == "linear":
            mobj = build_linear_nodes(cast(Scene, scene), labels, colors)
        elif kind == "target":
            rings = int(cast(int, spec.props.get("rings", 4)))
            max_radius = float(cast(float, spec.props.get("max_radius", 2.0)))
            mobj = create_target(
                cast(Scene, scene), rings=rings, max_radius=max_radius
            )
        else:
            mobj = build_cycle_nodes(cast(Scene, scene), labels, colors)

        position = spec.props.get("position")
        if position:
            mobj.move_to(cast(Sequence[float], position))

        cast(Scene, scene).play(Write(mobj))
        return mobj


def register_default_components(registry: object) -> None:
    if not isinstance(registry, ComponentRegistry):
        msg = f"Expected ComponentRegistry, got {type(registry).__name__}"
        raise TypeError(msg)
    registry.register("title", TitleComponent())
    registry.register("text", TextComponent())
    registry.register("diagram", DiagramComponent())
