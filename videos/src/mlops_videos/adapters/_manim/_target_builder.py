from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim import Scene, VGroup


class TargetBuilder:
    """Reusable patterns for building bullseye/dartboard visuals with Manim."""

    RING_COLORS = ("#FF0000", "#FFFFFF", "#FF0000", "#FFFFFF")
    BULLSEYE_COLOR = "#FF0000"

    @staticmethod
    def create_target(
        scene: Scene,
        rings: int = 4,
        max_radius: float = 2.0,
    ) -> VGroup:
        from manim import Circle, VGroup

        target = VGroup()
        for index in range(rings, 0, -1):
            r = max_radius * index / rings
            color = TargetBuilder.RING_COLORS[index % len(TargetBuilder.RING_COLORS)]
            circle = Circle(radius=r, color=color, stroke_width=3, fill_opacity=0.3)
            target.add(circle)
        return target

    @staticmethod
    def create_darts(
        scene: Scene,
        positions: Sequence[tuple[float, float]],
        color: str = "#FFFF00",
    ) -> VGroup:
        from manim import Circle, VGroup

        darts = VGroup()
        for x, y in positions:
            dot = Circle(radius=0.05, color=color, fill_opacity=1.0).move_to([x, y, 0])
            darts.add(dot)
        return darts

    @staticmethod
    def create_quadrant_grid(
        scene: Scene,
        labels: tuple[str, str, str, str] = ("Low Bias", "High Bias", "Low Bias", "High Bias"),
    ) -> VGroup:
        from manim import Line, Text, VGroup

        grid = VGroup()
        # Vertical and horizontal lines
        v_line = Line(start=[0, -3, 0], end=[0, 3, 0], color="#888888")
        h_line = Line(start=[-3, 0, 0], end=[3, 0, 0], color="#888888")
        grid.add(v_line, h_line)

        # Labels at quadrants
        positions = [
            [-2.5, 1.5, 0],  # Low Bias, Low Variance (top-left in quadrant terms)
            [2.5, 1.5, 0],  # High Bias, Low Variance
            [-2.5, -1.5, 0],  # Low Bias, High Variance
            [2.5, -1.5, 0],  # High Bias, High Variance
        ]
        for label, pos in zip(labels, positions, strict=True):
            text = Text(label, font_size=16).move_to(pos)
            grid.add(text)
        return grid
