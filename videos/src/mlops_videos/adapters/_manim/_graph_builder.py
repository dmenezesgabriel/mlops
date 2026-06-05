from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from manim import Axes, Scene, VGroup


class GraphBuilder:
    """Reusable patterns for mathematical plots with Manim."""

    @staticmethod
    def create_axes(
        scene: Scene,
        x_range: tuple[float, float, float] = (0, 10, 1),
        y_range: tuple[float, float, float] = (0, 10, 1),
    ) -> Axes:
        from manim import Axes

        return Axes(x_range=x_range, y_range=y_range)

    @staticmethod
    def plot_data(
        scene: Scene,
        axes: Axes,
        points: Sequence[tuple[float, float]],
        color: str = "#FFFF00",
        radius: float = 0.08,
    ) -> VGroup:
        from manim import Dot, VGroup

        dots = VGroup()
        for x, y in points:
            dot = Dot(color=color, radius=radius).move_to(axes.c2p(x, y))
            dots.add(dot)
        return dots

    @staticmethod
    def plot_curve(
        scene: Scene,
        axes: Axes,
        func: Callable[[float], float],
        x_range: tuple[float, float] = (0, 10),
        color: str = "#00FF00",
    ) -> object:
        return axes.plot(func, x_range=x_range, color=color)

    @staticmethod
    def plot_error_bars(
        scene: Scene,
        axes: Axes,
        x_values: Sequence[float],
        train_errors: Sequence[float],
        val_errors: Sequence[float],
        color: str = "#FF0000",
    ) -> VGroup:
        from manim import VGroup

        bars = VGroup()
        for x, te, ve in zip(x_values, train_errors, val_errors, strict=True):
            train_bar = axes.plot_line_graph(
                x_values=[x, x],
                y_values=[0, te],
                line_color="#00FF00",
                stroke_width=3,
            )
            val_bar = axes.plot_line_graph(
                x_values=[x, x],
                y_values=[te, te + ve],
                line_color="#FF0000",
                stroke_width=3,
            )
            bars.add(train_bar, val_bar)
        return bars

    @staticmethod
    def create_label(
        scene: Scene,
        text: str,
        position: tuple[float, float, float] = (0, 0, 0),
        font_size: int = 24,
    ) -> object:
        from manim import Text

        return Text(text, font_size=font_size).move_to(position)
