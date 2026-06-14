import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.infrastructure.manim.components import (  # noqa: E402
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

    def test_dimensions(self) -> None:
        import numpy as np

        labels = ("A", "B", "C")
        colors = ("#FF0000", "#00FF00", "#0000FF")
        result = build_cycle_nodes(None, labels, colors)
        # Verify that nodes are placed on a circle of radius 1.4
        for node in result:
            circle = node[0]
            center = circle.get_center()
            dist = np.linalg.norm(center)
            assert np.isclose(dist, 1.4)
            # Default node radius should be 0.4
            assert np.isclose(circle.radius, 0.4)


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

    def test_dimensions(self) -> None:
        import numpy as np

        result = create_target(None, rings=4)  # uses default max_radius
        # First circle added is the outermost circle (r = max_radius)
        outermost_circle = result[0]
        assert np.isclose(outermost_circle.radius, 1.3)
