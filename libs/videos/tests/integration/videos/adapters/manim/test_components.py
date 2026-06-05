import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.adapters.manim.components import (  # noqa: E402
    build_cycle_nodes,
    build_linear_nodes,
    create_target,
)


class TestBuildCycleNodes:
    def test_returns_vgroup(self) -> None:
        labels = ("A", "B", "C")
        colors = ("#FF0000", "#00FF00", "#0000FF")
        result = build_cycle_nodes(None, labels, colors)
        assert result is not None


class TestBuildLinearNodes:
    def test_returns_vgroup(self) -> None:
        labels = ("A", "B")
        colors = ("#FF0000", "#00FF00")
        result = build_linear_nodes(None, labels, colors)
        assert result is not None


class TestCreateTarget:
    def test_returns_vgroup(self) -> None:
        result = create_target(None, rings=4, max_radius=2.0)
        assert result is not None
