from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim import Scene, VGroup


class FlowBuilder:
    """Reusable patterns for building flow-diagram visuals with Manim."""

    @staticmethod
    def build_cycle(
        scene: Scene,
        labels: Sequence[str],
        colors: Sequence[str],
        radius: float = 0.6,
    ) -> VGroup:
        from manim import Circle, Text, VGroup

        n = len(labels)
        nodes = VGroup()
        for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
            angle = 2 * 3.14159 * index / n - 3.14159 / 2
            x = 2.5 * __import__("math").cos(angle)
            y = 2.5 * __import__("math").sin(angle)
            circle = Circle(radius=radius, color=color, fill_opacity=0.2).move_to([x, y, 0])
            text = Text(label, font_size=18).move_to(circle.get_center())
            nodes.add(VGroup(circle, text))
        return nodes

    @staticmethod
    def add_cycle_arrows(
        scene: Scene,
        nodes: VGroup,
        color: str = "#888888",
    ) -> VGroup:
        from manim import CurvedArrow, VGroup

        n = len(nodes)
        arrows = VGroup()
        for index in range(n):
            start = nodes[index].get_center()
            end = nodes[(index + 1) % n].get_center()
            arrow = CurvedArrow(start, end, radius=-2.0, color=color)
            arrows.add(arrow)
        return arrows

    @staticmethod
    def add_back_arrows(
        scene: Scene,
        nodes: VGroup,
        color: str = "#AAAAAA",
    ) -> VGroup:
        from manim import CurvedArrow, VGroup

        n = len(nodes)
        arrows = VGroup()
        for index in range(n):
            end = nodes[index].get_center()
            start = nodes[(index + 1) % n].get_center()
            arrow = CurvedArrow(
                start,
                end,
                radius=3.0,
                color=color,
                stroke_width=2,
                stroke_opacity=0.5,
            )
            arrows.add(arrow)
        return arrows

    @staticmethod
    def build_linear(
        scene: Scene,
        labels: Sequence[str],
        colors: Sequence[str],
    ) -> VGroup:
        from manim import Circle, Text, VGroup

        nodes = VGroup()
        right = __import__("manim").RIGHT
        for index, (label, color) in enumerate(zip(labels, colors, strict=True)):
            circle = Circle(radius=0.5, color=color, fill_opacity=0.2)
            circle.shift(2.0 * index * right)
            text = Text(label, font_size=16).move_to(circle.get_center())
            nodes.add(VGroup(circle, text))
        return nodes

    @staticmethod
    def add_linear_arrows(
        scene: Scene,
        nodes: VGroup,
        color: str = "#888888",
    ) -> VGroup:
        from manim import Arrow, VGroup

        n = len(nodes)
        arrows = VGroup()
        for index in range(n - 1):
            arrow = Arrow(
                start=nodes[index].get_right(),
                end=nodes[index + 1].get_left(),
                color=color,
            )
            arrows.add(arrow)
        return arrows
