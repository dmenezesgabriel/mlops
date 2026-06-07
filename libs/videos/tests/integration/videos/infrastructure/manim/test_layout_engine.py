import pytest

pytest.importorskip("manim")
pytestmark = pytest.mark.docker

from videos.domain.layout import LayoutRegion, LayoutSpec  # noqa: I001, E402
from videos.infrastructure.manim.layout_engine import ManimLayoutEngine  # noqa: I001, E402


class TestManimLayoutEngine:
    def test_validate_placement_returns_empty(self) -> None:
        engine = ManimLayoutEngine()
        layout = LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.BODY))
        errors = engine.validate_placement(layout)
        assert errors == []
