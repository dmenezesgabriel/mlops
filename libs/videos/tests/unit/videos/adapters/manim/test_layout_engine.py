from __future__ import annotations

import pytest

from videos.adapters.manim.layout_engine import ManimLayoutEngine
from videos.core.domain.layout import LayoutRegion, LayoutSpec
from videos.core.domain.scene_spec import ComponentSpec, SceneSpec


@pytest.fixture
def engine() -> ManimLayoutEngine:
    return ManimLayoutEngine()


def _minimal_scene(components: tuple[ComponentSpec, ...]) -> SceneSpec:
    return SceneSpec(
        scene_id="test",
        title="Test",
        goal="Test",
        duration_seconds=1.0,
        layout=LayoutSpec(regions=(LayoutRegion.TITLE, LayoutRegion.BODY)),
        components=components,
    )


class TestManimLayoutEngine:
    def test_apply_sets_title_position(self, engine: ManimLayoutEngine) -> None:
        comp = ComponentSpec(type="title", region="title")
        scene = _minimal_scene((comp,))

        result = engine.apply(scene)

        title_comp = result.components[0]
        assert "position" in title_comp.props
        # Assuming TITLE maps to UP * 3 (or [0, 3, 0])
        assert title_comp.props["position"] == [0, 3, 0]

    def test_apply_sets_body_position(self, engine: ManimLayoutEngine) -> None:
        comp = ComponentSpec(type="text", region="body")
        scene = _minimal_scene((comp,))

        result = engine.apply(scene)

        body_comp = result.components[0]
        assert "position" in body_comp.props
        # Assuming BODY maps to [0, 0, 0] or similar
        assert body_comp.props["position"] == [0, 0, 0]

    def test_apply_sets_diagram_position(self, engine: ManimLayoutEngine) -> None:
        comp = ComponentSpec(type="diagram", region="diagram")
        scene = _minimal_scene((comp,))

        result = engine.apply(scene)

        diag_comp = result.components[0]
        assert "position" in diag_comp.props
        # Assuming DIAGRAM maps to [0, -1, 0] or similar
        assert diag_comp.props["position"] == [0, -1, 0]
